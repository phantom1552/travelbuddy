"""
Checklist generation service using AI.

This service handles the business logic for generating personalized
trip checklists using the Groq API and AI models.
"""

import json
import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import uuid4

from app.models.trip import TripDataResponse, TransportType
from app.models.checklist import (
    ChecklistItemResponse,
    ChecklistGenerationResponse,
    PriorityLevel
)
from app.services.groq_client import GroqClient, GroqAPIError, GroqRateLimitError

logger = logging.getLogger(__name__)


class ChecklistGenerationError(Exception):
    """Custom exception for checklist generation errors."""
    pass


class ChecklistGeneratorService:
    """
    Service for generating AI-powered trip checklists.
    
    This service formats prompts for the AI model, parses responses,
    and provides fallback logic when AI generation fails.
    """
    
    def __init__(self, groq_client: GroqClient):
        """
        Initialize the checklist generator service.
        
        Args:
            groq_client: Configured Groq API client
        """
        self.groq_client = groq_client
        self.fallback_items = self._load_fallback_items()
    
    async def generate_checklist(
        self,
        trip_data: TripDataResponse
    ) -> ChecklistGenerationResponse:
        """
        Generate a personalized checklist for the given trip data.
        
        Args:
            trip_data: Trip information to generate checklist for
            
        Returns:
            Generated checklist with items and metadata
            
        Raises:
            ChecklistGenerationError: When generation fails completely
        """
        try:
            logger.info(f"Generating checklist for trip to {trip_data.location}")
            
            # Format the prompt for AI generation
            prompt = self._format_prompt(trip_data)
            
            # Generate AI response
            ai_response = await self.groq_client.generate_completion(
                prompt=prompt,
                max_tokens=1500,
                temperature=0.7
            )
            
            # Parse the AI response into checklist items
            items = self._parse_ai_response(ai_response)
            
            # If parsing failed or returned too few items, use fallback
            if not items or len(items) < 5:
                logger.warning("AI response parsing failed or insufficient items, using fallback")
                items = self._generate_fallback_items(trip_data)
            
            # Create the response
            checklist_id = str(uuid4())
            response = ChecklistGenerationResponse(
                id=checklist_id,
                items=items,
                generated_at=datetime.utcnow(),
                trip_data=trip_data
            )
            
            logger.info(f"Successfully generated checklist with {len(items)} items")
            return response
            
        except GroqRateLimitError:
            logger.warning("Rate limit exceeded, using fallback items")
            return self._create_fallback_response(trip_data)
            
        except GroqAPIError as e:
            logger.error(f"Groq API error: {str(e)}, using fallback items")
            return self._create_fallback_response(trip_data)
            
        except Exception as e:
            logger.error(f"Unexpected error during checklist generation: {str(e)}")
            raise ChecklistGenerationError(f"Failed to generate checklist: {str(e)}")
    
    def _format_prompt(self, trip_data: TripDataResponse) -> str:
        """
        Format a prompt for AI checklist generation.
        
        Args:
            trip_data: Trip information to include in prompt
            
        Returns:
            Formatted prompt string
        """
        # Build the base prompt
        prompt_parts = [
            "Generate a comprehensive packing checklist for a trip with the following details:",
            f"- Destination: {trip_data.location}",
            f"- Duration: {trip_data.days} day{'s' if trip_data.days != 1 else ''}",
            f"- Transportation: {trip_data.transport.value}",
            f"- Occasion/Purpose: {trip_data.occasion}"
        ]
        
        # Add optional details
        if trip_data.notes:
            prompt_parts.append(f"- Special notes: {trip_data.notes}")
        
        if trip_data.preferences:
            preferences_str = ", ".join(trip_data.preferences)
            prompt_parts.append(f"- Preferences: {preferences_str}")
        
        # Add formatting instructions
        prompt_parts.extend([
            "",
            "Please provide a JSON response with the following structure:",
            "{",
            '  "items": [',
            '    {',
            '      "text": "Item description",',
            '      "category": "Category name (e.g., Clothing, Electronics, Documents, Toiletries, etc.)",',
            '      "priority": "high|medium|low"',
            '    }',
            '  ]',
            "}",
            "",
            "Guidelines:",
            "- Include 15-25 relevant items",
            "- Categorize items logically",
            "- Consider the destination climate and culture",
            "- Account for the trip duration and transportation method",
            "- Include essential items like documents, medications, etc.",
            "- Prioritize items based on importance (high: essential, medium: recommended, low: optional)",
            "- Make items specific and actionable",
            "",
            "Return only the JSON response, no additional text."
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_ai_response(self, response: str) -> List[ChecklistItemResponse]:
        """
        Parse AI response into checklist items.
        
        Args:
            response: Raw AI response text
            
        Returns:
            List of parsed checklist items
        """
        try:
            # Clean the response - remove any markdown formatting
            cleaned_response = response.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
            
            # Try to find JSON in the response
            json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
            else:
                json_str = cleaned_response
            
            # Parse JSON
            parsed_data = json.loads(json_str)
            
            if not isinstance(parsed_data, dict) or "items" not in parsed_data:
                logger.error("Invalid JSON structure in AI response")
                return []
            
            items = []
            for item_data in parsed_data["items"]:
                if not isinstance(item_data, dict):
                    continue
                
                # Validate required fields
                if not all(key in item_data for key in ["text", "category"]):
                    continue
                
                # Create checklist item
                item = ChecklistItemResponse(
                    id=str(uuid4()),
                    text=str(item_data["text"]).strip(),
                    category=str(item_data["category"]).strip(),
                    checked=False,
                    priority=self._parse_priority(item_data.get("priority", "medium")),
                    user_added=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                items.append(item)
            
            logger.info(f"Successfully parsed {len(items)} items from AI response")
            return items
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from AI response: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error parsing AI response: {str(e)}")
            return []
    
    def _parse_priority(self, priority_str: str) -> PriorityLevel:
        """
        Parse priority string into PriorityLevel enum.
        
        Args:
            priority_str: Priority string from AI response
            
        Returns:
            PriorityLevel enum value
        """
        priority_lower = str(priority_str).lower().strip()
        
        if priority_lower in ["high", "essential", "critical", "important"]:
            return PriorityLevel.HIGH
        elif priority_lower in ["low", "optional", "nice-to-have"]:
            return PriorityLevel.LOW
        else:
            return PriorityLevel.MEDIUM
    
    def _generate_fallback_items(self, trip_data: TripDataResponse) -> List[ChecklistItemResponse]:
        """
        Generate fallback checklist items when AI generation fails.
        
        Args:
            trip_data: Trip information to customize fallback items
            
        Returns:
            List of fallback checklist items
        """
        logger.info("Generating fallback checklist items")
        
        # Get base fallback items
        base_items = self.fallback_items.copy()
        
        # Customize based on trip data
        customized_items = []
        
        for item_template in base_items:
            # Skip items not relevant to transport type
            if self._should_skip_item_for_transport(item_template, trip_data.transport):
                continue
            
            # Create the item
            item = ChecklistItemResponse(
                id=str(uuid4()),
                text=item_template["text"],
                category=item_template["category"],
                checked=False,
                priority=PriorityLevel(item_template["priority"]),
                user_added=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            customized_items.append(item)
        
        # Add transport-specific items
        transport_items = self._get_transport_specific_items(trip_data.transport)
        customized_items.extend(transport_items)
        
        # Add duration-specific items (prioritize these for long trips)
        if trip_data.days > 7:
            duration_items = self._get_long_trip_items()
            customized_items.extend(duration_items)
        
        # Limit to 25 items, but ensure we keep the most important ones
        if len(customized_items) > 25:
            # Sort by priority (high first) and keep top 25
            priority_order = {"high": 0, "medium": 1, "low": 2}
            customized_items.sort(key=lambda x: priority_order.get(x.priority.value, 1))
            customized_items = customized_items[:25]
        
        return customized_items
    
    def _should_skip_item_for_transport(self, item: Dict[str, Any], transport: TransportType) -> bool:
        """Check if an item should be skipped based on transport type."""
        # Skip car-specific items for air travel
        if transport == TransportType.PLANE and "car" in item["text"].lower():
            return True
        
        # Skip plane-specific items for car travel
        if transport == TransportType.CAR and any(word in item["text"].lower() for word in ["boarding", "flight", "airport"]):
            return True
        
        return False
    
    def _get_transport_specific_items(self, transport: TransportType) -> List[ChecklistItemResponse]:
        """Get items specific to the transport type."""
        items = []
        now = datetime.utcnow()
        
        if transport == TransportType.PLANE:
            plane_items = [
                {"text": "Boarding passes (printed or mobile)", "category": "Documents", "priority": "high"},
                {"text": "Passport or ID", "category": "Documents", "priority": "high"},
                {"text": "Travel-sized toiletries (3-1-1 rule)", "category": "Toiletries", "priority": "medium"},
                {"text": "Entertainment for flight", "category": "Electronics", "priority": "low"}
            ]
            for item_data in plane_items:
                items.append(ChecklistItemResponse(
                    id=str(uuid4()),
                    text=item_data["text"],
                    category=item_data["category"],
                    checked=False,
                    priority=PriorityLevel(item_data["priority"]),
                    user_added=False,
                    created_at=now,
                    updated_at=now
                ))
        
        elif transport == TransportType.CAR:
            car_items = [
                {"text": "Driver's license", "category": "Documents", "priority": "high"},
                {"text": "Car registration and insurance", "category": "Documents", "priority": "high"},
                {"text": "Phone car charger", "category": "Electronics", "priority": "medium"},
                {"text": "Snacks for the road", "category": "Food", "priority": "low"}
            ]
            for item_data in car_items:
                items.append(ChecklistItemResponse(
                    id=str(uuid4()),
                    text=item_data["text"],
                    category=item_data["category"],
                    checked=False,
                    priority=PriorityLevel(item_data["priority"]),
                    user_added=False,
                    created_at=now,
                    updated_at=now
                ))
        
        return items
    
    def _get_long_trip_items(self) -> List[ChecklistItemResponse]:
        """Get additional items for longer trips."""
        now = datetime.utcnow()
        long_trip_items = [
            {"text": "Extra underwear and socks", "category": "Clothing", "priority": "medium"},
            {"text": "Laundry detergent packets", "category": "Toiletries", "priority": "low"},
            {"text": "First aid kit", "category": "Health", "priority": "medium"}
        ]
        
        items = []
        for item_data in long_trip_items:
            items.append(ChecklistItemResponse(
                id=str(uuid4()),
                text=item_data["text"],
                category=item_data["category"],
                checked=False,
                priority=PriorityLevel(item_data["priority"]),
                user_added=False,
                created_at=now,
                updated_at=now
            ))
        
        return items
    
    def _create_fallback_response(self, trip_data: TripDataResponse) -> ChecklistGenerationResponse:
        """Create a fallback response when AI generation fails."""
        items = self._generate_fallback_items(trip_data)
        
        return ChecklistGenerationResponse(
            id=str(uuid4()),
            items=items,
            generated_at=datetime.utcnow(),
            trip_data=trip_data
        )
    
    def _load_fallback_items(self) -> List[Dict[str, Any]]:
        """
        Load fallback checklist items for when AI generation fails.
        
        Returns:
            List of fallback item templates
        """
        return [
            # Essential Documents
            {"text": "Passport or government-issued ID", "category": "Documents", "priority": "high"},
            {"text": "Travel insurance documents", "category": "Documents", "priority": "high"},
            {"text": "Hotel/accommodation confirmations", "category": "Documents", "priority": "high"},
            {"text": "Emergency contact information", "category": "Documents", "priority": "high"},
            
            # Clothing Essentials
            {"text": "Underwear (enough for trip duration + 2 extra)", "category": "Clothing", "priority": "high"},
            {"text": "Socks (enough for trip duration + 2 extra)", "category": "Clothing", "priority": "high"},
            {"text": "Weather-appropriate outerwear", "category": "Clothing", "priority": "medium"},
            {"text": "Comfortable walking shoes", "category": "Clothing", "priority": "medium"},
            {"text": "Sleepwear", "category": "Clothing", "priority": "medium"},
            
            # Health & Toiletries
            {"text": "Prescription medications", "category": "Health", "priority": "high"},
            {"text": "Toothbrush and toothpaste", "category": "Toiletries", "priority": "high"},
            {"text": "Deodorant", "category": "Toiletries", "priority": "medium"},
            {"text": "Shampoo and body wash", "category": "Toiletries", "priority": "medium"},
            {"text": "Sunscreen", "category": "Health", "priority": "medium"},
            
            # Electronics
            {"text": "Phone and charger", "category": "Electronics", "priority": "high"},
            {"text": "Camera or phone for photos", "category": "Electronics", "priority": "low"},
            {"text": "Portable power bank", "category": "Electronics", "priority": "medium"},
            
            # Money & Cards
            {"text": "Credit/debit cards", "category": "Money", "priority": "high"},
            {"text": "Cash in local currency", "category": "Money", "priority": "medium"},
            
            # Miscellaneous
            {"text": "Reusable water bottle", "category": "Miscellaneous", "priority": "medium"},
            {"text": "Travel pillow", "category": "Comfort", "priority": "low"},
            {"text": "Entertainment (books, tablets, etc.)", "category": "Entertainment", "priority": "low"}
        ]


# Global instance for dependency injection
def create_checklist_generator(groq_client: GroqClient) -> ChecklistGeneratorService:
    """Factory function to create checklist generator service."""
    return ChecklistGeneratorService(groq_client)