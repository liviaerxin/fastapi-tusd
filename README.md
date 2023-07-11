# Python Packaging with `setup.py`, `setup.cfg` and `pyproject.toml`

As known from the official documentation, most configuration in `setup.py` before should be moved to `setup.cfg` or `pyproject.toml` in the future!

The modern `backend`(such as `setuptools`) should recognize `setup.py`, `setup.cfg` and `pyproject.toml`.

Packaging stacks:

- frontend: pip, build, cibuildwheel
- backend: setuptools, distlib, flit, hatch
- publish: twine

[Configuring setuptools](https://setuptools.pypa.io/en/latest/userguide/index.html)

[Python Packaging with Setuptools. This article will explain the best… | by Insight in Plain Sight | ITNEXT](https://itnext.io/python-packaging-12ef040c4ea0)

[Packaging Python Projects — Python Packaging User Guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/)

## How to Develop a Python Package in Practices

When creating a Python project, developers usually want to implement and test changes iteratively, before cutting a release and preparing a distribution archive.

Most of time, we should stay in the [Development Mode](https://setuptools.pypa.io/en/latest/userguide/development_mode.html).

Firstly, prepare a development environment

```sh
python3 -m venv .venv
source ./venv/bin/activate
```

Secondly, manage the package's dependencies by adding them to `options.install_requires` field in `setup.cfg` file. Then run

```sh
# Use `-e` option to do Editable
pip install -e .

# Install `test` or `format` required packages
pip install -e .[test]
pip install -e .[format]
```

Optionally, if you add new dependencies, then run again

```sh
pip install -e .
```

Finally, when completing development, build and publish the distribution

```sh
# Build
pip install build
python -m build -s
python -m build

unzip -l ./dist/*.whl
```

```sh
# Publish
pip install twine
twine upload dist/*
```

## Getting started

A file resumable upload server implemented by FastAPI comply with the `tus` resumable upload protocol

Usage:

```sh
uvicorn app_tusd:app --reload
```

[GitHub - tus/tus-resumable-upload-protocol: Open Protocol for Resumable File Uploads](https://github.com/tus/tus-resumable-upload-protocol)
