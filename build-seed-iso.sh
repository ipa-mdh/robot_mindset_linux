mkdir seed
cp autoinstall.yaml seed/user-data
touch seed/meta-data
cp playbook.yaml seed

genisoimage \
  -output autoinstall-seed.iso \
  -volid CIDATA \
  -joliet -rock seed/
