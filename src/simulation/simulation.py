import logging
import os
import random as random
from collections import Counter
from datetime import timedelta
from copy import deepcopy
from seir.disease_state import DiseaseState

from simulation.event import DayEvent
from logs import Statistics, DayStatistics
from world import Person
from world.environments import InitialGroup


log = logging.getLogger(__name__)


class Simulation(object):
    """
    An object which runs a single simulation, holding a world,
    calling events and propagating infections throughout environments
    day by day.
    """
    __slots__ = (
        '_verbosity',
        '_world',
        '_date',
        '_initial_date',
        'interventions',
        '_events',
        'stats',
        'stop_early',
        'last_day_to_record_r',
        'num_r_days',
        'first_infectious_people',
        'initial_infection_doc',
        'num_days_to_run'
    )

    def __init__(self, world, initial_date, interventions=None, stop_early=None, verbosity=False,
                 outdir=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'outputs')):
        """
        :param world: The World object that this simulation will run on
        :param initial_date: The starting date for the simulation
        :param interventions: A list of the interventions applied in this simulation
        :param stop_early: An object that represent a condition which,
        when holds, causes the simulation to stop prematurely.
        Currently only one type of early stop supported, meant to help compute
        R0, R1, ..., Rk efficiently - stopping when all people infected in the
        first k days have recovered.
        :param verbosity: Whether or not this simulation should print debug info
        :param outdir: The path of the directory output files
        should be written into
        """
        if interventions is None:
            interventions = []
        self._verbosity = verbosity
        self._world = world
        self._date = initial_date
        self._initial_date = deepcopy(initial_date)
        self.interventions = interventions
        self._events = {}
        self.stats = Statistics(outdir, world)
        # It's important that we sign people up before we init interventions!
        self._world.sign_all_people_up_to_environments()
        for intervention in interventions:
            self.stats.add_intervention(intervention)

        # attributes relevant for computing R data
        self.stop_early = stop_early
        self.last_day_to_record_r = None
        self.num_r_days = None
        if self.stop_early is not None:
            name_stop, self.num_r_days = self.stop_early
            self.last_day_to_record_r = initial_date + timedelta(days=self.num_r_days)
            assert name_stop == "r", "Other premature stops are not yet supported"
        self.first_infectious_people = set()

        self.initial_infection_doc = None
        self.num_days_to_run = None

        # save all the events that create the interventions behavior on the simulation
        for inter in self.interventions:
            self.register_events(inter.generate_events(self._world))

    def simulate_day(self):
        """
        Simulate one day of the simulation. Does this in four steps:
        1. Apply or remove registered events
        (either applying intervention effects or
        advancing the disease states of people)
        2. register people who changed weights to their environments
        3. spread the infection throughout the environments
        4. register the changes to the Statistics object
        """
        if self._date in self._events:
            self._events[self._date].apply(self)
            del self._events[self._date]

        changed_population = [
            person for person in self._world.all_people() if person._changed
        ]

        for individual in changed_population:
            individual.register_to_daily_environments()

        for env in self._world.all_environments:
            self.register_events(env.propagate_infection(self._date))

        changed_population = [
            person for person in self._world.all_people() if person._changed
        ]

        if self._verbosity and self._date.weekday() == 6:
            log.info("------ day-{}: disease state ------------".format(self._date))
            log.info(Counter([person.get_disease_state() for person in self._world.all_people()]))
            log.info("------ Infected by environments ----------")
            log.info(Counter([person.get_infection_data().environment.name for person in self._world.all_people() if
                              person.get_disease_state().is_infected() and person.get_infection_data()]))

        daily_data = DayStatistics(
            self._date,
            changed_population
        )
        self.stats.add_daily_data(daily_data)
        for person in changed_population:
            person.save_state()

        if self.last_day_to_record_r is not None and self._date <= self.last_day_to_record_r:
            for person in changed_population:
                if person.is_infected:
                    self.first_infectious_people.add(person)
        self._date += timedelta(days=1)

    def register_event_on_day(self, event, date):
        """
        hook the given event to the given date, so in that day this event will happen.
        :param event: Event
        :param date: datetime Date
        """
        if date not in self._events:
            self._events[date] = DayEvent(date)
        self._events[date].hook(event)

    def register_events(self, event_list):
        """
        Add all the given events to their dates on the simulation.
        This applies only to DayEvents that need to be triggered on a specific date.
        :param event_list: list of Event objects
        """
        if not isinstance(event_list, list):
            event_list = [event_list]
        for event in event_list:
            assert isinstance(event, DayEvent), \
                'Unexpected event type: {}'.format(type(event))
            self.register_event_on_day(event, event._date)

    def infect_random_set(self, num_infected, infection_doc, per_to_immune=None, city_name=None,min_age=0):
        """
        Infect a uniformly random initial set,
        so that the disease can spread during the simulation.
        :param num_infected: int number of infected to make
        :param infection_doc: str to doc the infection data
        (written to the inputs.txt file)
        :param city_name: the name of the city to infect
        (if left None, infects people from all around the World)
        :param min_age: specify the min age from which we start to infect population
        if the value is 0 we infect all the population 
        """
        assert isinstance(num_infected, int)
        assert self.initial_infection_doc is None
        self.initial_infection_doc = infection_doc
        if per_to_immune is None:
            per_to_immune = 0.0
        if city_name is not None:
            population = [p for p in self._world.all_people() \
                if (p.get_city_name() == city_name)]
        else:
            population = [p for p in self._world.all_people()]

        num_immuned = int(round(len(population)*per_to_immune))
        assert len(population) >= num_infected + num_immuned \
            , "Trying to immune:{} infect:{} people out of {}".format(num_immuned, num_infected, len(population))
        
        used_persons = {}
        #First set the immune persons that are above min_age
        while num_immuned > 0: #we start to count from zero therefor we need one more person
            Selected_persons = random.sample(population, num_immuned)
            for p in Selected_persons:
                if (p.get_age() >= min_age) and (p.get_id() not in used_persons) : 
                    self.register_events(p.immune_and_get_events(self._date, InitialGroup.initial_group()))
                    num_immuned = num_immuned-1
                    used_persons[p.get_id()] = p
        for p in used_persons.values():
            print("id:" + str(p.get_id()) +" age:"+ str(p.get_age())) 

        #Second set the people that aren't immune to be infected
        while num_infected > 0:
            Selected_persons = random.sample(population, num_infected)
            for p in Selected_persons:
                if (p.get_id() not in used_persons) and (p.get_disease_state() == DiseaseState.SUSCEPTIBLE): 
                    self.register_events(p.infect_and_get_events(self._date, InitialGroup.initial_group()))
                    num_infected = num_infected-1

    def immune_households_infect_others(self,num_infected : int, infection_doc : str, per_to_immune=0.0, city_name=None,min_age = 0):
        """
        Immune some percentage of the households in the population and infectimg a given percentage of the population
        so that the disease can spread during the simulation.
        :param num_infected: int number of infected to make
        :param infection_doc: str to document the infection data
        (written to the inputs.txt file)
        :param city_name: the name of the city to infect
        (if left None, infects people from all around the World)
        :param min_age: specify the min age from which we start to infect population
        if the value is 0 we infect all the population 
        """
        assert isinstance(num_infected, int)
        assert self.initial_infection_doc is None
        self.initial_infection_doc = infection_doc
        if per_to_immune is None:
            per_to_immune = 0.0
        if city_name is not None:
            households = [h for h in self._world.get_all_city_households() if h._city == city_name]
        else:
            households = [h for h in self._world.get_all_city_households()]
        #Select houses immun 
        cnt_house_to_emmun = int(per_to_immune * len(households))
        random.shuffle(households)
        safe_group =households[0 : cnt_house_to_emmun]
        not_safe_group = households[cnt_house_to_emmun:]
        #Emmune people in the safe group
        for house in safe_group:
            for person in house.get_people():
                if person.get_age() >= min_age:
                    self.register_events(person.immune_and_get_events(self._date, InitialGroup.initial_group()))
        #Select num_infected persons from General population that was not infected(not_sage_group) and infect them 
        if num_infected > 0:
            UnsafePersons = [person for house in not_safe_group for person in house.get_people() \
             if person.get_disease_state() == DiseaseState.SUSCEPTIBLE]
            people_to_infect = random.sample(UnsafePersons, min(len(UnsafePersons),num_infected))
            for person in people_to_infect:
                self.register_events(person.infect_and_get_events(self._date, InitialGroup.initial_group()))
    
    def first_people_are_done(self):
        """
        chacks whether the people infected on the first “num_r_days” days
        are infected. We use this in simulations in which we try to compute R.
        When these people recover, we stop the simulation.
        """
        if self.stop_early is None:
            return False
        return all((not person.is_infected) for person in self.first_infectious_people)

    def infect_chosen_set(self, infection_datas, infection_doc):
        """
        Infect a chosen and specific set of people, given to the function, and register the events.
        :param infection_datas: list of (id, date, seit_times) for each person to infect
        :param infection_doc: str to doc the infection for inputs file
        """
        assert self.initial_infection_doc is None
        self.initial_infection_doc = infection_doc
        for person_id, infection_date, seir_times in infection_datas:
            p = self._world.get_person_from_id(person_id)
            events = p.infect_and_get_events(infection_date, InitialGroup.initial_group(), seir_times=seir_times)
            p.get_infection_data().date = None  # To avoid being asked to plot this date, which is out of our range
            self.register_events(events)

        original_date = self._date
        for date in sorted(self._events.keys()):
            if date < original_date:
                self._date = date
                self._events[date].apply(self)
                del self._events[date]
        self._date = original_date

    def run_simulation(self, num_days, name, datas_to_plot=None,run_simulation = None,extensionsList = None):
        """
        This main loop of the simulation.
        It advances the simulation day by day and saves,
        and after it finishes it saves the output data to the relevant files.
        :param num_days: int - The number of days to run
        :param name: str - The name of this simulation, will determine output
        directory path and filenames.
        :param datas_to_plot: Indicates what sort of data we wish to plot
        and save at the end of the simulation.
        :param Extension: user's class that contains function that is called at the end of each day
        """
        assert self.num_days_to_run is None
        self.num_days_to_run = num_days
        if datas_to_plot is None:
            datas_to_plot = dict()
        log.info("Starting simulation " + name)

        extensions = []
        if extensionsList != None:
            for ExtName in extensionsList:
                mod  = __import__('src.extensions.' + ExtName,fromlist=[ExtName])
                ExtensionType = getattr(mod,ExtName)
                extensions = extensions + [ExtensionType(self)]
            

        for day in range(num_days):
            for ext in extensions:
                ext.start_of_day_processing()

            self.simulate_day()
            #Call Extension function at the end of the day
            for ext in extensions:
                ext.end_of_day_processing()
                
            if self.stats.is_static() or self.first_people_are_done():
                if self._verbosity:
                    log.info('simulation stopping after {} days'.format(day))
                break
                

        self.stats.mark_ending(self._world.all_people())
        self.stats.calc_r0_data(self._world.all_people(), self.num_r_days)
        self.stats.dump('statistics.pkl')
        for name, data_to_plot in datas_to_plot.items():
            self.stats.plot_daily_sum(name, data_to_plot)
        self.stats.write_summary_file('summary')
        self.stats.write_summary_file('summary_long', shortened=False)
        if self.stats._r0_data:
            self.stats.plot_r0_data('r0_data_' + name)
        self.stats.write_params()
        self.stats.write_inputs(self)
        self.stats.write_interventions_inputs_csv()
        