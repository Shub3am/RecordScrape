from setuptools import setup, find_packages

setup(
    name="video-product-recorder",
    version="0.1.0",
    description="Automated video product recording tool",
    author="Your Name",
    packages=find_packages(),
    install_requires=[
        "playwright>=1.40.0",
        "pyyaml>=6.0",
        "jsonschema>=4.19.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "black",
            "flake8",
            "pre-commit",
        ]
    },
    python_requires=">=3.8",
)
