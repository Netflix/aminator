from setuptools import setup
setup(
    name = "aminator",
    version = "0.9.0",
    packages = ["aminator"],
    install_requires=[
        "boto>=2.7",
        "botocore>=0.4.2",
    ],
    scripts = ["bin/aminate", "bin/aminator.sh", "bin/aminator-funcs.sh"]
)
