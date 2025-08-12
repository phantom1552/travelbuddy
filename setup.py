from setuptools import setup, find_packages

setup(
    name="ai-trip-checklist-backend",
    version="1.0.0",
    description="Backend API for AI Trip Checklist App",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "fastapi==0.104.1",
        "uvicorn[standard]==0.24.0",
        "pydantic==2.5.0",
        "pydantic-settings==2.1.0",
        "python-jose[cryptography]==3.3.0",
        "passlib[bcrypt]==1.7.4",
        "python-multipart==0.0.6",
        "groq==0.4.1",
        "httpx==0.25.2",
        "pytest==7.4.3",
        "pytest-asyncio==0.21.1",
    ],
)