#!/bin/bash

OUTPUT_DIR=output
SEED_ISO=$OUTPUT_DIR/seed.iso

genisoimage \
  -output $SEED_ISO \
  -volid CIDATA \
  -joliet -rock $OUTPUT_DIR/seed/
