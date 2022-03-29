from tabula import convert_into
import csv
import os
import argparse
from countrycodes import ISOtoIOC
import country_converter as coco
import requests

# -----------------------------------------------------------------------------
# Argument parsing
parser = argparse.ArgumentParser()

parser.add_argument("-y", "--year", help="specify the year", type=int, required=True)
parser.add_argument("-r", "--round", help="specify the round", type=int, required=True)
parser.add_argument("-c", "--country", help="specify the IOC country code (in case the program couldn't figure it out)", type=str)

args = parser.parse_args()

# -----------------------------------------------------------------------------
# Get country code for round (Looks like the FIA uses IOC country codes instead of ISO)
if args.country:
	ioc_code = args.country.lower()
elif args.year == 2020 and args.round in [1, 2]:
	ioc_code = "aut{}".format(args.round)
else:
	country_name = requests.get("http://ergast.com/api/f1/{}/{}.json".format(args.year, args.round)).json()['MRData']['RaceTable']['Races'][0]['Circuit']['Location']['country']
	if country_name == "UK":
		country_name = "GBR"
	elif country_name == "UAE":
		country_name = "ARE"

	iso_code = coco.convert(country_name, to="ISO3")
	ioc_code = iso_code

	try:
		ioc_code = ISOtoIOC[iso_code]
	except:
		None
	ioc_code = ioc_code.lower()


# -----------------------------------------------------------------------------
# Fetch the PDFs
lap_analysis_file_url = 'https://www.fia.com/sites/default/files/{}_{:02d}_{}_f1_r0_timing_racelapanalysis_v01.pdf'.format(args.year, args.round, ioc_code)
race_history_file_url = 'https://www.fia.com/sites/default/files/{}_{:02d}_{}_f1_r0_timing_racehistorychart_v01.pdf'.format(args.year, args.round, ioc_code)

# Convert to CSV
lap_analysis_file_name = 'linear-lap-times.csv'
race_history_file_name = 'linear-race-history.csv'

convert_into(lap_analysis_file_url, lap_analysis_file_name, lattice=True, pages = "all")
convert_into(race_history_file_url, race_history_file_name, lattice=True, pages = "all")

lap_analysis_file = csv.reader(open(lap_analysis_file_name))
race_history_file = list(csv.reader(open(race_history_file_name)))

# Lap Analysis
all_lap_times = []
lap_times = []
lap_analysis_file = list(lap_analysis_file)[2:]
lap_counter = '0'
for i in range(len(lap_analysis_file)):
	row = lap_analysis_file[i]
	if len(row) == 3:
		if row[0] == '1'and i != 0:
			all_lap_times.append(lap_times)
			lap_times = []
			lap_counter = '0'
		if row[2] != '' and row[0] != lap_counter:
			lap_times.append(row[2])
			# We keep track of which laps we've got, since the FIA document may write down the same lap twice (see 2022 Saudi Arabian GP)
			lap_counter = row[0]
all_lap_times.append(lap_times)

def getNumber(string):
	if string.isdigit():
		return int(string)
	else:
		return -1

# Get list of drivers who completed at least one lap
def set_of_driver_numbers_with_laps():
	return set(filter(lambda x: x > -1, map(lambda x: getNumber(x[0]),race_history_file[2:])))
	# for row in list(race_history_file)[2:(len(all_drivers) + 2)]:
		# driver_number = row[0]

from reigningchampion import reigning_champion_number

# List of constructors
constructors = requests.get("http://ergast.com/api/f1/{}/{:02d}/constructors.json".format(args.year, args.round)).json()['MRData']['ConstructorTable']['Constructors']
constructor_ids = list(map(lambda x: x['constructorId'], constructors))
constructor_for_driver = {}
driver_numbers_sorted_by_constructor = []



driver_numbers = []

# Associate each driver with a constructor
for constructor in constructor_ids:
	drivers = constructors = requests.get("http://ergast.com/api/f1/{}/{:02d}/constructors/{}/drivers.json".format(args.year, args.round, constructor)).json()['MRData']['DriverTable']['Drivers']
	# all_drivers.extend(drivers)
	constructor_driver_numbers = list(map(lambda x: x['permanentNumber'], drivers))
	
	
	# Ergast data only knows a driver's permanent number and will not indicate when the champion opts to race with the number '1'
	# Check to see if the reigning WDC races with the number '1'
	for i in range(len(constructor_driver_numbers)):
		number = constructor_driver_numbers[i]
		if reigning_champion_number[args.year].get(number) != None:
			constructor_driver_numbers[i] = reigning_champion_number[args.year].get(number)

	driver_numbers.extend(constructor_driver_numbers)
	# for n in map(lambda x: str(x), sorted(map(lambda x: int(x), driver_numbers))):
	for n in map(str, sorted(map(int, constructor_driver_numbers))):
		constructor_for_driver[n] = constructor
		driver_numbers_sorted_by_constructor.append(n)

# List of driver numbers
driver_numbers = list(map(int, driver_numbers))
driver_numbers_sorted = sorted(driver_numbers)
driver_laps = {}
driver_numbers_with_no_laps = set(driver_numbers) - set_of_driver_numbers_with_laps()

print(driver_numbers)
print(driver_numbers_with_no_laps)
print(set_of_driver_numbers_with_laps())


# Associate lap times from Lap Analysis to the correct drivers
times_skipped = 0
for i in range(len(driver_numbers)):
	driver = str(driver_numbers_sorted[i])
	if driver_numbers_sorted[i] in driver_numbers_with_no_laps:
		times_skipped += 1
		driver_laps[driver] = []
		continue
	driver_laps[driver] = all_lap_times[i - times_skipped]


# Use Race History Chart to get the lap times for lap 1
drivers_completed_lap_1 = []
for row in race_history_file[2:(len(driver_numbers) + 2)]:
	driver_number = row[0]
	if driver_number in drivers_completed_lap_1:
		break
	drivers_completed_lap_1.append(driver_number)
	lap_time = row[2]
	if len(driver_laps[driver_number]) > 0:
		driver_laps[driver_number][0] = lap_time

# Save to csv
total_laps = max([len(x) for x in driver_laps.values()])
with open('lap-times.csv', mode='w') as output_file:
	output_file.write(",".join(str(x) for x in driver_numbers))
	output_file.write("\n")
	for lap in range(total_laps):
		laps = [driver_laps[str(driver)][lap] if len(driver_laps[str(driver)]) > lap else "" for driver in driver_numbers]
		output_file.write(",".join(str(x) for x in laps))
		output_file.write("\n")

# Remove temporary working files
os.remove(lap_analysis_file_name)
os.remove(race_history_file_name)

# -----------------------------------------------------------------------------
# Convert laptime strings into ints
from datetime import datetime

def str_to_seconds(string):
	try:
		return (datetime.strptime(string, '%M:%S.%f') - datetime(1900,1,1)).total_seconds()
	except:
		return 0.0


for driver_number in driver_numbers:
	driver_laps[str(driver_number)] = list(map(str_to_seconds, driver_laps[str(driver_number)]))


# -----------------------------------------------------------------------------
# Graph Drawing
def median(lst):
	sortedLst = sorted(lst)
	lstLen = len(lst)
	index = (lstLen - 1) // 2

	if (lstLen % 2):
		return sortedLst[index]
	else:
		return (sortedLst[index] + sortedLst[index + 1]) / 2.0

filtered_lap_times = list(filter(lambda x: len(x) > 0, driver_laps.values()))
median_lap_time = median(list(map(lambda x: median(x), filtered_lap_times)))
print("Baseline lap time: ", median_lap_time)

# Cumulative lap time
import copy
driver_cumulative_lap_times = copy.deepcopy(driver_laps)
for driver in driver_cumulative_lap_times.keys():
	laps = driver_cumulative_lap_times[driver]
	if len(laps) <= 1:
		continue
	for i in range(1, len(laps)):
		laps[i] = sum(driver_laps[driver][0:(i+1)])
	laps = list(map(lambda x: round(x, 3), laps))
	driver_cumulative_lap_times[driver] = laps


# Delta to baseline car
delta_to_baseline_car = copy.deepcopy(driver_cumulative_lap_times)
for driver in delta_to_baseline_car.keys():
	cumulative_times = delta_to_baseline_car[driver]
	for i in range(len(cumulative_times)):
		cumulative_times[i] -= (i + 1) * median_lap_time
	cumulative_times = list(map(lambda x: round(x, 3), cumulative_times))
	delta_to_baseline_car[driver] = cumulative_times

import matplotlib.pyplot as plt
from constructorcolours import colour_for_constructor
from math import ceil, floor
import numpy as np
from matplotlib.font_manager import FontProperties

fontP = FontProperties()
fontP.set_size('xx-small')

plt.style.use('dark_background')
fig = plt.figure()
ax = fig.add_subplot(1, 1, 1)

all_deltas = [item for sublist in delta_to_baseline_car.values() for item in sublist]
ymin = floor(min(all_deltas) / 10) * 10
ymax = ceil(max(all_deltas) / 10) * 10
yticks = np.arange(ymin, ymax, 10)
ymajorticks = np.arange(floor(ymin / 60) * 60, ceil(ymax / 60) * 60, 60)


ax.set_xticks(list(range(total_laps + 1)), minor=True)
ax.set_yticks(yticks, minor=True)
ax.set_yticks(ymajorticks)

for i in range(len(driver_numbers_sorted_by_constructor)):
	driver = driver_numbers_sorted_by_constructor[i]
	deltas = delta_to_baseline_car[driver]
	linestyle = '-' if i % 2 == 0 else '--'
	plt.plot(list(range(1, len(deltas) + 1)), deltas, label=driver, color=colour_for_constructor[args.year][constructor_for_driver[driver]], linestyle = linestyle)

plt.suptitle("{} Round {} - {}".format(args.year, args.round, ioc_code.upper()))
plt.title("Baseline lap time: {} s".format(median_lap_time), fontsize='small')
plt.legend(title='Drivers', bbox_to_anchor=(1, 1), loc='upper left', prop=fontP)

plt.grid(True, 'both', 'both', color="grey", alpha=0.3)
ax.grid(which='major', alpha=0.5)
plt.gca().invert_yaxis()
plt.show()