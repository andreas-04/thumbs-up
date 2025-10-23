# Quick Start

## Setup python virtual environment

### Activating

Linux/macos
```bash
cd internal/
python3 --version # version must be 3+
python3 -m venv .venv # create the virtual env
source .venv/bin/activate # activate the virtual env
```
Windows
```bash
cd internal/
python --version # version must be 3+
python -m venv .venv # create the virtual env
.\.venv\Scripts\Activate.ps1 # activate the virtual env
```

### Installing Existing Dependencies

```bash
python3 -m pip install --upgrade pip
pip install -r scripts/dependencies.txt
```

### Installing New Dependencies

```bash
python3 -m pip install <package> 
# update dep list
pip freeze > scripts/dependencies.txt
```