from setuptools import setup, find_packages

setup(
    name="curl-mcp",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "mcp-core>=1.0.0",
        "rich>=10.0.0"
    ],
    entry_points={
        "console_scripts": [
            "curl-mcp=__main__:main"
        ]
    }
)