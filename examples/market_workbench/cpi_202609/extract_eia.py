"""Extract the pre-cutoff EIA rows used here; optional dependency: xlrd."""
import csv
from pathlib import Path
import xlrd

RAW = Path(__file__).resolve().parent / 'research/raw'
book = xlrd.open_workbook(RAW/'eia_gasoline_weekly.xls')
sheet = book.sheet_by_name('Data 1')
assert 'All Grades All Formulations' in sheet.cell_value(2, 1)
rows = []
for i in range(3, sheet.nrows):
    values = sheet.row_values(i)
    if not isinstance(values[0], (float, int)):
        continue
    date = xlrd.xldate_as_datetime(values[0], book.datemode).date().isoformat()
    if '2026-07-01' <= date <= '2026-09-16':
        rows.append({'observation_date': date, 'GASALLW': values[1]})
with (RAW/'gasoline_primary.csv').open('w') as f:
    writer = csv.DictWriter(f, fieldnames=['observation_date', 'GASALLW'])
    writer.writeheader()
    writer.writerows(rows)
print(f'Extracted {len(rows)} weekly observations, ending {rows[-1]["observation_date"]}.')
