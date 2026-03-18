import pandas as pd
import os
import math

#config
#create new folder split_files for the output. Keep CSV file and python together.
INPUT_FILE = "directories_big_file.csv"   # path to a big CSV file which we need to split into smaller files
OUTPUT_DIR = "split_files"                # folder where chunks will be saved
ROWS_PER_FILE = 50_000                    # rows per chunk (adjust as needed) - Try more rows if possible - output less csv files
#

os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"Reading {INPUT_FILE} ...")
df = pd.read_csv(INPUT_FILE)

total_rows = len(df)
total_chunks = math.ceil(total_rows / ROWS_PER_FILE)

print(f"Total rows   : {total_rows:,}")
print(f"Rows per file: {ROWS_PER_FILE:,}")
print(f"Files to create: {total_chunks}")
print()

for i in range(total_chunks):
    start = i * ROWS_PER_FILE
    end   = min(start + ROWS_PER_FILE, total_rows)
    chunk = df.iloc[start:end]

    filename = os.path.join(OUTPUT_DIR, f"chunk_{i+1:03d}_of_{total_chunks:03d}.csv")
    chunk.to_csv(filename, index=False)

    size_mb = os.path.getsize(filename) / (1024 * 1024)
    print(f"  ✓ {filename}  ({end - start:,} rows, {size_mb:.1f} MB)")

print()
print("Files saved to:", os.path.abspath(OUTPUT_DIR))
