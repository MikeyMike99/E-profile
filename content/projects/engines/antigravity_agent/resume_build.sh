#!/bin/bash
TARGET="robert@172.20.10.3"

echo "Please get ready to type your password for Robert's machine now."
sleep 3

# Added -q to silence the massive block of OpenSSH warnings so the screen reader hits the password prompt instantly
ssh -q -o ServerAliveInterval=60 -o ServerAliveCountMax=30 $TARGET 'cmd.exe /c "cd DevCore_Build && python remote_compiler.py"'

echo ""
echo "Compilation finished! Please get ready to type the password one last time to retrieve the file."
sleep 3

scp -q $TARGET:~/DevCore_Build/Siraugga.exe /mnt/c/Users/michael/Documents/DevCore/

echo "Build Complete! Siraugga.exe is ready."
