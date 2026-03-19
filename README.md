# The ABC of AKM

[![arXiv](https://img.shields.io/badge/arXiv-2603.17034-b31b1b.svg)](https://arxiv.org/abs/2603.17034) [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tlamadon/abc-of-akm/blob/main/jep.ipynb) [![View Notebook](https://img.shields.io/badge/View-Notebook-blue)](https://tlamadon.github.io/abc-of-akm/) [![Download PDF](https://img.shields.io/badge/Download-PDF-red)](https://tlamadon.github.io/abc-of-akm/jep.pdf)

Companion notebook to "A Users Guide to Uncovering Worker and Firm Effects: The ABC of AKM" by Bonhomme, Lamadon and Manresa for the Journal of Economic Perspectives.

## Running the notebook

### Option 1: Google Colab (no installation needed)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tlamadon/abc-of-akm/blob/main/jep.ipynb)

Click the badge above to open and run the notebook directly in your browser.

### Option 2: Run locally

You will need Python 3 and the [Graphviz](https://graphviz.org/) system library installed.

**Install Graphviz:**

- macOS: `brew install graphviz`
- Ubuntu/Debian: `sudo apt-get install graphviz`

**Set up the environment and run:**

```bash
git clone https://github.com/tlamadon/abc-of-akm.git
cd abc-of-akm
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
jupyter notebook jep.ipynb
```
