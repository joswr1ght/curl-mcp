from setuptools import setup, find_packages

setup(
    name="curl-mcp",
    version="1.0.0",
    description="Natural Language Curl Commander for MCP",
    author="MartinPSDev",
    packages=find_packages(),
    install_requires=[
        "httpx>=0.28.1",
        "mcp[cli]>=1.6.0",
        "rich>=10.0.0"
    ],
    entry_points={
        "console_scripts": [
            "curl-mcp=main:mcp.run"
        ]
    },
    python_requires=">=3.13",
)