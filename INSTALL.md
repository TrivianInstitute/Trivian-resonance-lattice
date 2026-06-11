# Installation & Setup

## Requirements

- Python 3.10 or higher
- No external dependencies required for core functionality

## Quick start

Clone and run the interactive demo:

```bash
git clone https://github.com/TrivianInstitute/trivian-resonance-lattice
cd trivian-resonance-lattice
python examples/demo.py
```

## Install as a library

```bash
pip install -e .
```

Then in your code:

```python
from trivian_resonance_lattice.interface.gaian_interface import GaianNode, GaianInterface
```

## Optional: cryptographic node verification

For Ed25519 signature verification (production deployments):

```bash
pip install cryptography
```

Then inject the verifier — see `core/signature_verifier.py` for the injection pattern.

## Run the tests

```bash
python tests/test_field_core.py    # 36 tests — ethical kernel
python tests/test_lattice.py       # 32 tests — full lattice stack
```

All 68 tests pass with no external dependencies.

## Repository structure

```
core/           Ethical kernel and trust primitives
lattice/        Network topology and signal propagation
interface/      Breath entrainment and embodied interaction
examples/       Interactive REPL demo
tests/          Test suite
docs/           Architecture and research documentation
```

See `ARCHITECTURE.md` for the full technical and philosophical design document.

## Contact

Institute: [connect@trivianinstitute.org](mailto:connect@trivianinstitute.org)
Research: trivianinstitute.org
Field site: trivianfield.com
