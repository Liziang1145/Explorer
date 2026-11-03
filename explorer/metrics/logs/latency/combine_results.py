import csv
from pathlib import Path

root = Path(__file__).resolve().parent
rows = []
for name in ('trials_55.csv', 'trials_45.csv'):
    with (root/name).open(encoding='utf-8-sig', newline='') as handle:
        rows.extend(csv.DictReader(handle))
with (root/'trials_55.csv').open(encoding='utf-8-sig', newline='') as handle:
    fields = csv.DictReader(handle).fieldnames
for index, row in enumerate(rows, 1):
    row['trial'] = index
with (root/'trials_100.csv').open('w', encoding='utf-8-sig', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
print(f'combined={len(rows)}')
