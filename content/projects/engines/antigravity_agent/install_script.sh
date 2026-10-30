#!/bin/bash
/mnt/c/Users/michael/Documents/antigravity_test/venv/bin/python3 -m pip install presidio-analyzer presidio-anonymizer spacy
/mnt/c/Users/michael/Documents/antigravity_test/venv/bin/python3 -m spacy download en_core_web_lg
echo "Done" > /mnt/c/Users/michael/Documents/antigravity_test/install_done.txt
