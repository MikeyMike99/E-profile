cd playground/Zip-Files
echo "Cracking file-1.zip (B)..."
time fcrackzip -u -c aA1 -l 1-4 file-1.zip
echo "Cracking file-2.zip (R2)..."
time fcrackzip -u -c aA1 -l 1-4 file-2.zip
echo "Cracking file-3.zip (0B1)..."
time fcrackzip -u -c aA1 -l 1-4 file-3.zip
echo "Cracking file-4.zip (Y0Da)..."
time fcrackzip -u -c aA1 -l 1-4 file-4.zip
echo "Cracking file-5.zip (C-3P0)..."
time fcrackzip -u -c aA1 -p '-' -l 1-5 file-5.zip
