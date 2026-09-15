from setuptools import setup, find_packages

setup(
    name="cachyos-update-center",
    version="1.0.0",
    author="Julian / CachyOS Community",
    description="Modernes Update Center für CachyOS mit vorheriger Spiegelserver-Bewertung",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "PyQt6>=6.4.0",
    ],
    entry_points={
        "console_scripts": [
            "cachyos-update-center=cachyos_update_center.app:main",
        ],
    },
)
