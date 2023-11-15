# F1 Race Lap Chart

A Python script that produces race lap charts for Formula One races from the 2018 season onwards.
The chart plots each driver's gap to an imaginary car driving at a constant reference lap time instead of their gap to the race leader.

It extracts the race lap times from the Race Lap Analysis and Race History Chart PDFs that the FIA produce after each event.

The script uses the [Ergast API](https://ergast.com/mrd) to look up which drivers and constructors were entered for each event. In addition to the license of this repository, please see their [terms and conditions](https://ergast.com/mrd/terms/).

# Usage

```
lap-times.py [-h] -y YEAR -r ROUND [-c COUNTRY]

options:
  -h, --help            show this help message and exit
  -y YEAR, --year YEAR  specify the year
  -r ROUND, --round ROUND
                        specify the round
  -c COUNTRY, --country COUNTRY
                        specify the IOC country code (in case the program couldn't figure it out)
```