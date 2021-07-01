from datetime import date
import json 
import numpy as np
import os
import pandas as pd 
from scipy.stats import sem

from simulation.params import Params
from simulation.simulation import Simulation
from world.population_generation import population_loader
from world.city_data import cities, get_city_list_from_dem_xls
from world.population_generation import generate_city

#const to save the amount of age groups we have 0..4,5,,9 and so on 
GROUP_COUNT = 16
#How many times we generate the city and doing average upon
REPS_NUM = 50

def count(city_arrays):
    # convert each person to their age group,
    for house_index in range(len(city_arrays)):
        for prsn_index in range(len(city_arrays[house_index])):
            city_arrays[house_index][prsn_index] = min(GROUP_COUNT - 1, city_arrays[house_index][prsn_index] // 5)
    ret = np.zeros((GROUP_COUNT,GROUP_COUNT))  
    for i in range(GROUP_COUNT):
        #count the number of i's in the array
        acc =0
        for house in city_arrays:
            if i in house:
                for age in house:
                    if age==i:
                        acc += 1
        for j in range(GROUP_COUNT):
            cnt_j = 0 
            for house in city_arrays: 
                if j in house:
                    if not(j==i):
                        cnt_house_i = 0
                        cnt_house_j = 0
                        for age in house:
                            if age == i:
                                cnt_house_i += 1
                            if age == j:
                                cnt_house_j += 1
                        cnt_j += cnt_house_i * cnt_house_j
                    else:
                        cnt_house_i = 0
                        for age in house:
                            if age == i:
                                cnt_house_i += 1
                        cnt_j += cnt_house_i * (cnt_house_i-1)
            if (acc == 0):
                ret[i][j] = 0
            else: 
                ret[i][j] = cnt_j / acc 
    return ret

def generate_cities(city_name:str):
    #Generate city 
    INITIAL_DATE = date(year=2020, month=2, day=27)
    config_path = os.path.join(os.path.dirname(__file__),"config.json")
    with open(config_path) as json_data_file:
        ConfigData = json.load(json_data_file)
        citiesDataPath = ConfigData['CitiesFilePath']
        paramsDataPath = ConfigData['ParamsFilePath']
    
    Params.load_from(os.path.join(os.path.dirname(__file__), paramsDataPath), override=True)
       
    cities = []
    for i in range(REPS_NUM):
        pop = population_loader.PopulationLoader(
                citiesDataPath,
                added_description="",
                with_caching=False,
                verbosity=False
            )

        cityArr = []
        tmp_city = pop.get_city_by_name(city_name)
        my_world = generate_city(city = tmp_city,
                            is_smart_household_generation=False,
                            internal_workplaces=True,
                            scaling=1.0,
                            verbosity=False,
                            to_world=True)
        my_world.sign_all_people_up_to_environments()
        
        #Generate array of array of household ages 
        for house in my_world.get_all_city_households():
            house_ages = []
            for p in house.get_people():
                house_ages.append(p.get_age())
            cityArr.append(house_ages)
    
        #Calc 50 matrixes from which we will calc the avg and error 
        cities.append(count(cityArr))
    return cities

def calc_avg(cities):
    #Calc avg matrix 
    avg_mat = np.zeros((GROUP_COUNT,GROUP_COUNT))
    for i in range(len(cities)):
        avg_mat = avg_mat + cities[i]
    avg_mat = avg_mat / REPS_NUM
    return avg_mat

def calc_sem(cities):
    #Calc sem matrix    
    sem_mat = np.zeros((GROUP_COUNT,GROUP_COUNT))
    for i in range(GROUP_COUNT):
        for j in range(GROUP_COUNT):
            tmp =np.zeros(REPS_NUM)
            for t in range(REPS_NUM):
                tmp[t] =cities[t][i][j]
            sem_mat[i][j] = sem(tmp)
    return sem_mat

def save(avg_mat,sem_mat,city_name:str)->None:
    #Print results 
    catgories = ["0..4","5..9","10..14","15..19","20..24","25..29","30..34", \
        "35..39","40..44","45..49","50..54","55..59","60..64","65..69","70..74","75+"]
    avgDF = pd.DataFrame(avg_mat,columns= catgories,index= catgories)
    semDF = pd.DataFrame(sem_mat,columns= catgories,index= catgories)

    avgDF.to_csv(os.path.join(os.path.dirname(__file__),"outputs",city_name+"_avg.csv"))
    semDF.to_csv(os.path.join(os.path.dirname(__file__),"outputs",city_name+"_sem.csv"))
    

def main():
    city_name = 'Bene Beraq'
    cities = generate_cities(city_name)
    avg_mat = calc_avg(cities)
    sem_mat = calc_sem(cities)
    save(avg_mat=avg_mat,sem_mat=sem_mat,city_name = city_name)


if __name__ =="__main__":
    main()
    