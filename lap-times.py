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
# Fetch the PDF

fiaRound = args.round

# The 2023 Emilia Romagna GP was cancelled, but the FIA documents names documents using the rounds from the orignal calendar 
if args.year == 2023 and args.round > 5:
	fiaRound += 1
race_history_file_url = 'https://www.fia.com/sites/default/files/{}_{:02d}_{}_f1_r0_timing_racehistorychart_v01.pdf'.format(args.year, fiaRound, ioc_code)


# Convert to CSV
race_history_file_name = 'linear-race-history.csv'
convert_into(race_history_file_url, race_history_file_name, lattice=True, pages = "all")

# lap_analysis_file = csv.reader(open(lap_analysis_file_name))
race_history_file = list(csv.reader(open(race_history_file_name)))

event_name = race_history_file[0][0]

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

# print(driver_numbers)

for driver in driver_numbers:
	driver_laps[str(driver)] = []

# Get each driver's lap times
for row in race_history_file:
	if len(row) < 3:
		continue
	driver = row[0]
	lap_time = row[2]
	driver_laps[driver].append(lap_time)

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
import copy
import numpy as np
# Graph Drawing
def median(lst):
	sortedLst = sorted(lst)
	lstLen = len(lst)
	index = (lstLen - 1) // 2
	if (lstLen % 2):
		return sortedLst[index]
	else:
		return (sortedLst[index] + sortedLst[index + 1]) / 2.0

# Baseline lap time
filtered_lap_times = list(filter(lambda x: len(x) > 0, driver_laps.values()))
baseline_lap_time = round(median(list(map(lambda x: median(x), filtered_lap_times))))

# Cumulative lap time
driver_cumulative_lap_times = copy.deepcopy(driver_laps)
for driver in driver_cumulative_lap_times.keys():
	laps = driver_cumulative_lap_times[driver]
	if len(laps) <= 1:
		continue
	for i in range(1, len(laps)):
		laps[i] = sum(driver_laps[driver][0:(i+1)])
	laps = list(map(lambda x: round(x, 3), laps))
	driver_cumulative_lap_times[driver] = laps

# Disrupted Periods
# Try to automatically detect when the race has been disrupted (VSC, SC, Red Flag)

# Leader(s) lap times
leaders_lap_times = []
lap_one_times = sorted([(d, driver_laps[d][0] if len(driver_laps[d])>0 else 100000) for d in driver_laps.keys()], key=lambda x: x[1])

ordered_driver_numbers = [x[0] for x in lap_one_times]
leader = ordered_driver_numbers[0]

# Find the drivers on the lead lap
for lap in range(total_laps):
	cumulative_times_for_driver = []
	driver_numbers = list(driver_cumulative_lap_times.keys())

	for driver in ordered_driver_numbers:
		if len(driver_cumulative_lap_times[driver]) > lap:
			leader = driver
			break
	
	for driver in driver_numbers:
		if len(driver_cumulative_lap_times[driver]) <= lap:
			continue
		cumulative_time = driver_cumulative_lap_times[driver][lap]
		
		lap_starts_on_lead_lap = driver_cumulative_lap_times[driver][lap-2] < driver_cumulative_lap_times[leader][lap-1] if lap > 1 else True
		if not (lap_starts_on_lead_lap):
			# Driver is lapped
			continue
		cumulative_times_for_driver.append((driver, cumulative_time))
	# Sort by position
	s = sorted(cumulative_times_for_driver, key=lambda x: x[1])
	ordered_driver_numbers, _ = zip(*s)
	ordered_driver_numbers = list(ordered_driver_numbers)
	leaders_lap_times.append([(d, driver_laps[d][lap]) for d in ordered_driver_numbers[0:len(ordered_driver_numbers)]])


yellow_laps = []
sc_laps = [] # a subset of yellow_laps
red_laps = []
yellow_threshold = baseline_lap_time * 1.1
red_threshold = 600

baseline_lap_times = [baseline_lap_time for _ in range(total_laps)]

# TODO: Identify rain-affected laps
# Currently, rain-affected laps are identified as VSC periods and have adjusted baseline lap times, which they shouldn't have
# See 2020 R14 Turkish GP, 2018 R11 German GP, 2021 R15 Russian GP

# Identify disrupted laps
for lap in range(total_laps):
	lap_times_of_leaders = [x[1] for x in leaders_lap_times[lap]]
	# print()
	# print(lap + 1)
	# print(lap_times_of_leaders)
	# print(np.corrcoef(np.arange(0, len(lap_times_of_leaders)), lap_times_of_leaders)[0][1], np.sqrt(np.var(lap_times_of_leaders)))
	median_lap_time = median(lap_times_of_leaders)
	if median_lap_time > red_threshold:
		red_laps.append(lap)
	elif median_lap_time > yellow_threshold:
		yellow_laps.append(lap)

# Adjust baseline lap times to suit the occasion
# Leader becomes the baseline under SC and Red Flags
# Leader doesn't become the baseline under VSC
for lap in sorted(yellow_laps + red_laps):
	median_lap_time = median([x[1] for x in leaders_lap_times[lap]])
	leader = leaders_lap_times[lap][0][0]
	last_driver_on_lead_lap = leaders_lap_times[lap][-1][0]
	spread = driver_cumulative_lap_times[last_driver_on_lead_lap][lap] - driver_cumulative_lap_times[leader][lap]

	# The baseline lap time so that the leader becomes the baseline
	neutralising_baseline_lap_time = driver_cumulative_lap_times[leader][lap] - sum(baseline_lap_times[0:lap])
	if lap in yellow_laps:
		last_vsc_lap = lap+1 not in yellow_laps and lap-1 not in sc_laps
		red_flag_restart = lap-1 in red_laps

		if red_flag_restart:
			baseline_lap_times[lap] = neutralising_baseline_lap_time
		elif (leaders_lap_times[lap][0][1] > median_lap_time or spread < 60) and not last_vsc_lap:
			# Safety Car
			sc_laps.append(lap)
			baseline_lap_times[lap] = neutralising_baseline_lap_time
		else:
			# VSC
			if lap-1 in yellow_laps and lap-1 not in sc_laps:
				# Baseline lap time is constant for a given VSC period
				baseline_lap_times[lap] = baseline_lap_times[lap-1]
			else:
				baseline_lap_times[lap] = median_lap_time
	else:
		# Red flag lap
		baseline_lap_times[lap] = neutralising_baseline_lap_time


# Delta to baseline car
delta_to_baseline_car = copy.deepcopy(driver_cumulative_lap_times)
for driver in delta_to_baseline_car.keys():
	cumulative_times = delta_to_baseline_car[driver]
	for i in range(len(cumulative_times)):
		cumulative_times[i] -= sum(baseline_lap_times[0:i+1])#(i + 1) * baseline_lap_time
	cumulative_times = list(map(lambda x: round(x, 3), cumulative_times))
	delta_to_baseline_car[driver] = cumulative_times

import matplotlib.pyplot as plt
from constructorcolours import colour_for_constructor
from math import ceil, floor
from matplotlib.font_manager import FontProperties

fontP = FontProperties()
fontP.set_size('xx-small')

plt.style.use('dark_background')
fig = plt.figure()
ax = fig.add_subplot(1, 1, 1)

all_deltas = [item for sublist in delta_to_baseline_car.values() for item in sublist]
deltas_without_anomalous_laps = list(filter(lambda x: x < red_threshold, all_deltas))
ymin = floor(min(all_deltas) / 10) * 10
ymax = ceil(max(all_deltas) / 10) * 10
yticks = np.arange(ymin, ymax, 10)
ymajorticks = np.arange(floor(ymin / 60) * 60, ceil(ymax / 60) * 60, 60)


ax.set_xticks(list(range(total_laps + 1)), minor=True)
ax.set_yticks(yticks, minor=True)
ax.set_yticks(ymajorticks)

ax.set_xlim([0, total_laps+1])
ax.set_ylim([ymin-5, ceil(max(deltas_without_anomalous_laps) / 10) * 10 + 5])

start_laps = [0] + red_laps + [total_laps]

for i in range(len(driver_numbers_sorted_by_constructor)):
	driver = driver_numbers_sorted_by_constructor[i]
	deltas = delta_to_baseline_car[driver]
	red_flag_split_deltas = []
	laps_to_plot = []
	for j in range(len(start_laps)-1):
		deltas_to_add = deltas[start_laps[j]:start_laps[j+1]]
		laps_to_add = range(start_laps[j]+1, start_laps[j+1]+1)[:len(deltas_to_add)]
		if j != 0:
			deltas_to_add = deltas_to_add[1:]
			laps_to_add = laps_to_add[1:] 
		red_flag_split_deltas.append(deltas_to_add)
		laps_to_plot.append(laps_to_add)
	linestyle = '-' if i % 2 == 0 else '--'
	for j in range(len(red_flag_split_deltas)):
		d = red_flag_split_deltas[j]
		plt.plot(laps_to_plot[j], d, label=driver if j == 0 else '', color=colour_for_constructor[args.year][constructor_for_driver[driver]], linestyle = linestyle)

plt.suptitle(event_name)#"{} Round {} - {}".format(args.year, args.round, ioc_code.upper()))
plt.title("Baseline lap time: {} s".format(baseline_lap_time), fontsize='small')
plt.legend(title='Drivers', bbox_to_anchor=(1, 1), loc='upper left', prop=fontP)

plt.grid(True, 'both', 'both', color="grey", alpha=0.3)
ax.grid(which='major', alpha=0.5)
for lap in red_laps:
	plt.axvspan(lap, lap+1, color='red', alpha=0.3, lw=0)
for lap in yellow_laps:
	plt.axvspan(lap, lap+1, color='yellow', alpha=0.25, lw=0)
for lap in sc_laps:
	plt.axvspan(lap, lap+1, color='yellow', alpha=0.15, lw=0)
plt.gca().invert_yaxis()
plt.show()