#!/bin/bash
mv /home/michael/.local/bin/agy /home/michael/.local/bin/agy_real
cat << 'EOF' > /home/michael/.local/bin/agy
#!/bin/bash
echo "AGY CALLED WITH: $@" >> /mnt/c/Users/michael/Documents/DevCore/agy_args.log
for arg in "$@"; do
    echo "ARG: $arg" >> /mnt/c/Users/michael/Documents/DevCore/agy_args.log
done
exec /home/michael/.local/bin/agy_real "$@"
EOF
chmod +x /home/michael/.local/bin/agy
