from setuptools import setup, find_packages

setup(
    name="dockervm",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "dockervm_cli": ["templates/**/*", "templates/**/.*"],
    },
    install_requires=[
        "typer[all]",
        "rich",
        "questionary",
    ],
    entry_points={
        "console_scripts": [
            "dockervm=dockervm_cli.main:app",
            "dvm=dockervm_cli.main:app",
        ],
    },
    author="D4rk-Sh4dw",
    description="Ein modernes CLI-Tool zur Verwaltung Ihrer Docker-VM.",
)
