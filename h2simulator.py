#!/bin/python3
import numpy as np
import matplotlib.pyplot as plt
import datetime as dt
import calendar
import random
from matplotlib.figure import Figure
from matplotlib.collections import LineCollection
from matplotlib.ticker import FixedLocator,AutoMinorLocator
from tkinter import *
import tkinter as tk
from PIL import ImageTk,Image
import pandas as pd
import threading
import os
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

class Simulation:

    def __init__(self):
        self.pv=self.importcfg("pv")
        self.elyzer=self.importcfg("elyzer")
        self.bat=self.importcfg("bat")
        self.storage=self.importcfg("storage")
        self.general=self.importcfg("general")
        self.input=self.importcfg("input")
        self.fcell=self.importcfg("fcell")
        self.sinks=self.importcfg("sinks")
        self.opti=self.importcfg("opti")
        self.modules=[self.general.keys()]
        self.dataset={}
        self.initial=[0,0,0]
        self.solar=self.importData()
        self.labels=self.mklabels()
        self.heatdays=0
        self.loadarray=self.ranload()
        self.sim={'pvintot' : 0, 'onmod' : 0,\
        'bcharge' : 0, 'scharge' : 0, \
        'elbought' : 0, 'elsold' : 0, \
        'gabought' : 0, 'pvin' : 0, 'tload' : 0, \
        'toth' : 0, 'etime' : 0, 'ftime' : 0}
        self.shw={'pvintot' : 0, 'onmod' : 0,\
        'bcharge' : 0, 'scharge' : 0, \
        'elbought' : 0, 'elsold' : 0, \
        'gabought' : 0, 'pvin' : 0 , \
        'xaxis' : '', 'LOG' : 0}
        self.sum={} #{'Electricity cost' : 0, 'Autonomy rate (E)' : 0, \
#        'Money saved (E)' : 0, 'CO2 avoided (E)' : 0, 'Gas cost' : 0, \
#        'Autonomy rate (G)' : 0, 'Money saved (G)' : 0, 'CO2 avoided (G)' : 0, \
#        "Total avoided CO2 (kg)" : 0, "Total avoided CO2 (kg)" : 0}
        self.tsum={}

    def importcfg(self, module):
        dic={}
        with open("config/{}.cfg".format(module), "r") as f:
            for line in f:
                (key, value) = line.split(',')
                dic[key.strip()] = (value.strip('\n').strip())   
        f.close()
        return dic
        
    def importData(self):
        S=self
        hrfr=int(S.input['Datapoint frequency (per hour)'])
        y=int(S.input['Year column'])-1
        m=int(S.input['Month column'])-1
        d=int(S.input['Day column'])-1
        h=int(S.input['Hour column'])-1
        n=int(S.input['Minute column'])-1
        k=int(S.input['Input column'])-1
        fname=S.input['Filename']
        itype=S.input['Input Type (power (kW) / irradiance (W/m2))']
        parea=float(S.pv['Total Area (m2)'])
        peffi=float(S.pv['Efficiency (%)'])/100
        data=np.loadtxt("{}".format(fname), delimiter=',', skiprows=1)
        diic={}
        i=0
        for line in data:
                i+=1
                year,month,day=int(line[y]),int(line[m]),int(line[d])
                hour,minute=int(line[h]),int(line[n])
                if i==1:
                        S.initial=[year,month,day]
                if itype != 'power':
                        inp=float(line[k])*peffi*parea/1000   #Convert to kW
                else:
                        inp=float(line[k])
                diic["{}-{}-{};{}:{}".format(year,month,day,hour,minute)]=inp
        return diic

    def mklabels(self):
        labels={'pvintot' : 'Total Power in AC (kWh)', 'onmod' : 'Electrolyzers running (# modules)',\
        'bcharge' : 'Battery charge (kWh)', 'scharge' : 'Hydrogen stored (kg)', \
        'elbought' : 'Electricity bought (kWh)', 'elsold' : 'Electricity sold (kWh)', \
        'gabought' : 'Gas bought (m^3)', 'pvin' : 'Current power in AC (kW)' }
        return labels
        
    def ranload(self):
        S=self
        random.seed()
        mn,mx=6,60 #Min / Max Power consumption in kW
        m,n=90,450 #Min / Max Energy consumption per day in kWh
        hrfr=int(S.input['Datapoint frequency (per hour)'])
        total=float(S.sinks['Electricity Consumption per year (kWh)'])
        bload = float(S.sinks['Electricity base load (kW)'])
        ntotal=total-bload*8760
        ar=np.random.randint(int(mx/mn),size=12*hrfr)
        ar=ar*mn/hrfr
        num=random.randrange(m,n)/np.sum(ar)
        o=ar*num
        for i in range(365):
            ar=np.random.randint(int(mx/mn),size=12*hrfr)
            ar=ar*mn/hrfr
            num=random.randrange(m,n)/np.sum(ar)
            o=np.vstack([o,ar*num])
        #print(o)
        #print(np.sum(o))
        p=o.flatten()
        q=p*ntotal/np.sum(p)
        return q
        
    def electrolyze(self, kwh):
        S=self
        etype=S.elyzer["Type (PEM/AEM)"]
        emods=float(S.elyzer['Number of Modules'])
        ekw=float(S.elyzer['Module Power (kW)'])
        onmod=float(S.sim['onmod'])
        scharge=float(S.sim['scharge'])
        scap=float(S.storage['Total Capacity  (kg)'])
        hrfr=float(S.input['Datapoint frequency (per hour)'])
        whkg=float(S.elyzer['Conversion Rate (kWh/m3)'])*11   #Because 11m^3 are 1 kg of H2
        if etype == 'PEM':
            opra=.1
        if etype == 'AEM':
            opra=.6
        #calculate consumption
        cons=ekw*onmod/hrfr
        #See if storage is at capacity
        if scharge<scap*.99:
            if cons*(opra)>kwh:           #Need battery power
                    b=S.batter(1,(cons*(opra)-kwh))
                    h=S.store(0,cons*(opra)/whkg)
            else:                        #Charge battery
                    b=S.batter(0,max(kwh-cons,0))
                    h=S.store(0,min(kwh,cons)/whkg)
        else:
            b=S.batter(0,kwh)
            S.sim['onmod']=0
            
    def batter(self,cha,kwh):
        S=self
        bcap=float(S.bat['Total Capacity  (kWh)'])
        bcharge=float(S.sim['bcharge'])
        hrfr=float(S.input['Datapoint frequency (per hour)'])
        beff=float(S.bat['Full cycle efficiency (%)'])/100
        if S.general['bat']=='0':
            bcap=0
        if cha==1:
            bcharge-=kwh
        else:
            bcharge+=kwh*beff
        if bcharge >= bcap:
            S.grid(0,bcharge-bcap)
            bcharge=bcap
            #print('bat full')
            x=1
        elif bcharge < 0:
            S.grid(1,-bcharge)
            bcharge=0
            x=-1
        else:
            x=0
        S.sim['bcharge']=bcharge
        return x
        
    def store(self,cha,kg):
        S=self
        scap=float(S.storage['Total Capacity  (kg)'])
        chacost=float(S.storage['Charging Cost (kWh/kg)'])
        dchacost=float(S.storage['Discharging Cost (kWh/kg)'])
        hrfr=float(S.input['Datapoint frequency (per hour)'])
        scharge=float(S.sim['scharge'])
        toth=float(S.sim['toth'])
        if cha==1:
            scharge-=kg
            S.batter(1,dchacost*kg)
        else:
            scharge+=kg
            S.batter(1,chacost*kg)
            toth+=kg
        if scharge >= scap*.99:
            scharge=min(scharge,scap)
            #print('H2 full')
            x=1
        elif scharge < .01*scap:
            #print('H2 empty')
            scharge=max(scharge,0)
           # hem+=1
            x=-1
        else:
            x=0
        S.sim['scharge']=scharge
        S.sim['toth']=toth
#        return x
        
    def fuelcell(self,kwh):
        S=self
        hrfr=float(S.input['Datapoint frequency (per hour)'])
        kwkg=float(S.fcell['Conversion Rate (kWh/kg)'])
        mxpw=float(S.fcell['Maximum Power (kW)'])/hrfr
        scharge=float(S.sim['scharge'])
        kgused=kwh/kwkg
        if S.general['fcell'] == '0':
            S.grid(1,(kwh))
        else:
            if kwh>mxpw:
                S.grid(1,(kwh-mxpw))
                kgused=mxpw/kwkg
            if scharge>0 and mxpw>0:
                S.sim['ftime']+=1/hrfr
            if kgused>scharge:
                S.sim['scharge']=0
                S.grid(1,(kgused-scharge)*kwkg)
                #print('not enough H2 for Power, bought',(kgused-scharge)*kwkg*hrfr)
            else:
                x=S.store(1,kgused)
            
            
        
    def heating(self,month):
        S=self
        hrfr=float(S.input['Datapoint frequency (per hour)'])
        scharge=float(S.sim['scharge'])
        mixrat=float(S.sinks['max H2 portion in mix (%)'])
        #heating period:
        mn, mx = S.sinks['Heating period (Month - Month)'].split('-')
        #Amount= N m3 / year 
        totalkg=float(S.sinks['Gas Consumption per year (m^3)'])/11 #11m^3 per kg H2
        year=int(S.initial[0])
        ldom=calendar.monthrange(year,int(mx))[1] #last day of the month where still heating is necessary
        d0=dt.date(year,int(mx),ldom)-dt.date(year,1,1)
        d1=dt.date(year,12,31)-dt.date(year,int(mn),1)
        days=float((d0+d1).days)
        S.heatdays=days
        kgperday=totalkg/days
        kgs=kgperday/12/hrfr
        #print(kgperday,kgs,days)
        if (int(month) <= int(mx) or int(month) >= int(mn)):
            if S.general['storage']=='0':
                S.grid(2,kgs)
            else:
                kgsh=kgs*mixrat/100
                S.grid(2,kgs-kgsh)
                if kgsh>scharge:            #print('not enough H2 in tank')
                    S.sim['scharge']=0
                    S.grid(2,kgsh-scharge)
                else:
                    S.store(1,kgsh)

    def load(self,kwh,idx):
        S=self
        hrfr=float(S.input['Datapoint frequency (per hour)'])
        total=float(S.sinks['Electricity Consumption per year (kWh)'])
        bload = float(S.sinks['Electricity base load (kW)'])/hrfr
        bcharge=S.sim['bcharge']
        array=S.loadarray
        if idx>=0:
            load=array[idx]+bload
        else:
            load=bload
        if load > kwh:
            lft=load-kwh
            if lft > bcharge:
                #print('going for battery', lft)
                S.sim['bcharge']=0
                S.fuelcell(lft-bcharge)
            else:
                S.batter(1,lft)
            ret=0
        else:
            ret=kwh-load
        return ret
            
            
    def grid(self,cha,kwh):
        S=self
        hrfr=float(S.input['Datapoint frequency (per hour)'])
        cost=float(S.sinks['Electricity Cost from grid (Eur/kWh)'])
        gain=float(S.sinks['Revenue from selling to grid (Eur/kWh)'])
        elbought=float(S.sim['elbought'])
        elsold=float(S.sim['elsold'])
        gabought=float(S.sim['gabought'])
        if cha==1: #If need electricity from grid
            elbought+=abs(kwh)
            S.sim['elbought']=elbought
        elif cha==0:      #If sell electricity to grid
            elsold+=kwh
            S.sim['elsold']=elsold
        else: #Buy Gas from grid
            gas=gabought+11*kwh
            S.sim['gabought']=gas
            
            
        
    def run(self):
        global fulldic
        S=self
        #Get Parameters
        hrfr=float(S.input['Datapoint frequency (per hour)'])
        emods=float(S.elyzer['Number of Modules'])
        ekw=float(S.elyzer['Module Power (kW)'])
        scap=float(S.storage['Total Capacity  (kg)'])
        onmod=float(S.sim['onmod'])
        bcap=float(S.bat['Total Capacity  (kWh)'])
        bload = float(S.sinks['Electricity base load (kW)'])/hrfr
        if S.general['bat']=='0':
            bcap=0
        S.sim['scharge']=float(S.storage['Initial charge (kg)'])
        loarray=S.loadarray
        #Initialize simulation
        year,month,day=self.initial
        hour,minute=0,0
        fullray=[]
        fulldic={}
        i,r=0,0
        inc=int(60/hrfr)
        dyear=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[0])
        dmonth=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[1])
        dday=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[2])
        while dyear==year:#dmonth<5: #
#               date=str(dt.date(dyear,dmonth,day)+dt.timedelta(days=i))
                hour,minute=0,0

                while hour<24:
                    
                    datestring="{}-{}-{};{}:{}".format(dyear,dmonth,dday,hour,minute)
                    tempdic={}
                    if S.general['pv']=='1':
                        try:    #See if there is input from the panels
                                kw=float(S.solar[datestring])
                        except:
                                kw=0
                    else:
                        kw=0
                    kwh=kw/hrfr
                    pv=float(S.sim['pvintot'])+kwh
                    S.sim['pvin']=kwh
                    S.sim['pvintot']=pv
                    if hour >=7 and hour<19:
                        rem=S.load(kwh,r)     #Pay electricity load from PV, Storage, or grid
                        S.sim['tload']=S.sim['tload']+loarray[r]+bload
                        r+=1 #Increase index for load randomizers
                        S.heating(dmonth)        #Use H2 for heating or buy from grid if tank empty
                    else:
                        rem=S.load(kwh,-1)     #Pay electricity load from PV, Storage, or grid
                        S.sim['tload']=S.sim['tload']+bload
                    if (rem>0 and S.general['elyzer']=='1') or ((S.sim['bcharge'])>0 and S.general['elyzer']=='1'): #If there is PV power left, run electrolyzer
                        S.electrolyze(rem)
                    elif rem>0 and S.general['bat']=='1':
                        S.batter(0,rem)
                    elif rem>0:
                        S.grid(0,rem)
                    #onmod=S.sim['onmod']
                    #bcharge=S.sim['bcharge'] 
                    #scharge=S.sim['scharge']
                    #elbought=S.sim['elbought']
                    pvintot,onmod, bcharge, scharge, elbought, elsold, gabought, pvin, tload, toth, etime, ftime=S.sim.values()
                    if rem-onmod*ekw/hrfr>ekw/hrfr and onmod<emods and S.general['elyzer']=='1' and scharge<scap*.99 and bcharge>=onmod*0.1*bcap:
                        onmod+=1
                        S.sim['onmod']=onmod
                    elif (onmod>0 and S.general['bat']=='1' and bcharge<0.01*bcap) or (rem<=0 and onmod>0 and S.general['bat']=='0'):
                        onmod-=1
                        S.sim['onmod']=onmod
                    if onmod>0:
                        #print('high times', times)
                        S.sim['etime']=etime+1/hrfr
                        etime=S.sim['etime']
#                    fullray.append([dyear,dmonth,dday,hour,minute,0])
                    tempdic={'pvintot' : pv, 'onmod' : onmod, 'bcharge' : bcharge, 'scharge' : scharge, \
                    'elbought' : elbought, 'elsold' : elsold, 'gabought' : gabought, 'pvin' : kw, 'tload' : tload, 'toth' : toth, 'etime' : etime, 'ftime' : ftime}
                    fulldic[datestring]=tempdic
                    S.dataset[datestring]=tempdic
                    #if minute==0 and hour==13:	#hour==12 and minute==0:
                        #print(dmonth,dday,hour,S.sim)    
                        #print(dmonth,dday,hour,fulldic[datestring])
                    if minute+inc>59:
                            hour+=1
                            minute=0
                    else:
                            minute+=inc
                #print(datestring, S.sim)
                i+=1 #Next day
                dyear=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[0])
                dmonth=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[1])
                dday=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[2])
        fullray=np.asarray(fullray)
        S.final=datestring
        #print(S.sim['tload'])
        #print('haha',fulldic['2020-12-17;5:25'])
        return fulldic
        
    def plotx(self,x,y,date,show):
        S=self
        x=np.asarray(x)
        fig, ax= plt.subplots(1)
        c=0
        for key in show.keys():
        	if show[key]==1:
        		ax.plot(x,y[:,c], label='{}'.format(S.labels[key]))
        	c+=1
        #ax.plot(x,y[:,2], label='kWh Batterieladung')
        #ax.plot(x,y[:,7], label='kWh PV Produktion')
        fig.set_size_inches(6,6)
        ax.set_xlabel(show['xaxis'])
        ax.set_ylabel('Values')
        ax.set_title('Values on {}'.format(date))
        #ax.set_xticks(np.arange(0,mx+10,10))
        #ax.set_yticks(np.arange(0,5000,250))
        ax.grid()
        ax.legend()
        #ax.set_yscale('log')
        #fig.savefig('Fullsim2.pdf')
        return fig
                    
    def plotDay(self,year,month,day,show={},i=0):
        S=self
        hrfr=float(S.input['Datapoint frequency (per hour)'])
        hour,minute=0,0
        #i=0
        x,y=[],[]
        #show=S.shw
        #show['pvin']=1
        #show['bcharge']=1
        #show['scharge']=1
        #show['xaxis']='Hour of the day'
        #print(show, 'hyyy')
        inc=int(60/hrfr)
        dyear=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[0])
        dmonth=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[1])
        dday=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[2])
        datestring="{}-{}-{};{}:{}".format(dyear,dmonth,dday,hour,minute)
        sdic=fulldic[datestring]
        while hour<24:           
                datestring="{}-{}-{};{}:{}".format(dyear,dmonth,dday,hour,minute)
                dic=fulldic[datestring]
                ldic=dic
                keys=dic.keys()
                x.append(hour+minute/60)
                #print(datestring,dic)
                g=[]
                for k in keys:
                        g.append(dic[k])
                y.append([*g])
                if minute+inc>59:
                    hour+=1
                    minute=0
                else:
                    minute+=inc
        x=np.asarray(x)
        y=np.asarray(y)
        elss=ldic['elsold'] - sdic['elsold']
        elbs=ldic['elbought'] - sdic['elbought']
        gabs=ldic['gabought'] - sdic['gabought']
        tlods=ldic['tload'] - sdic['tload']
        S.sumry('day',dmonth,elss,elbs,gabs,tlods)
        return Mplot(x,y,'Values on {}-{}-{}'.format(dyear,dmonth,dday),show,S.labels)
        
    def plotMonth(self,year,month,show={}):
        S=self
        hrfr=float(S.input['Datapoint frequency (per hour)'])
        hour,minute=12,0
        day=1
        i=-1
        if month ==1:
            i=0
        x,y=[],[]
        inc=int(60/hrfr)
        subkeys=['elsold','elbought', 'gabought']
        dyear=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[0])
        dmonth=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[1])
        dday=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[2])
        datestring="{}-{}-{};{}:{}".format(dyear,dmonth,dday,hour,minute)
        dic=fulldic[datestring]
        sdic=S.savedic(dic)
        i+=1
        dmonth=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[1])
        dday=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[2])
        while dmonth==month:
            datestring="{}-{}-{};{}:{}".format(dyear,dmonth,dday,hour,minute)
            #dic=S.dataset[datestring]
            dic2=fulldic[datestring]
            ldic=S.savedic(dic2)
            keys=dic.keys()
            x.append(dday)
            #print(datestring,dic)
            g=[]
            for k in keys:
                    if k in subkeys:
                        g.append(dic2[k]-dic[k])
                    elif k == 'pvin':
                        g.append(dic2['pvintot']-dic['pvintot'])
                    else:
                        g.append(dic2[k])
            y.append([*g])
            dic=S.savedic(dic2)
            i+=1
            dmonth=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[1])
            dday=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[2])
            dyear=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[0])
        x,y=np.asarray(x),np.asarray(y)
        elss=ldic['elsold'] - sdic['elsold']
        elbs=ldic['elbought'] - sdic['elbought']
        gabs=ldic['gabought'] - sdic['gabought']
        tlods=ldic['tload'] - sdic['tload']
        S.sumry('month',month,elss,elbs,gabs,tlods)
        return Mplot(x,y,'Values from {}-{} until {}-{}'.format(year,month,dyear,dmonth),show,S.labels)

    def plotYear(self,year,month,show={}):
        S=self
        hrfr=float(S.input['Datapoint frequency (per hour)'])
        hour,minute=12,0
        day=1
        i=-1
        if month ==1:
            i=0
        x,y=[],[]
        inc=int(60/hrfr)
        subkeys=['elsold','elbought', 'gabought']
        dyear=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[0])
        dmonth=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[1])
        dday=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[2])
        datestring="{}-{}-{};{}:{}".format(dyear,dmonth,dday,hour,minute)
        dic=fulldic[datestring]
        sdic=S.savedic(dic)
        i+=1
        dmonth=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[1])
        dday=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[2])
        while dyear==year:
            datestring="{}-{}-{};{}:{}".format(dyear,dmonth,dday,hour,minute)
            #dic=S.dataset[datestring]
            dic2=fulldic[datestring]
            ldic=S.savedic(dic2)
            keys=dic.keys()
            x.append(i)
            #print(datestring,dic)
            g=[]
            for k in keys:
                    if k in subkeys:
                        g.append(dic2[k]-dic[k])
                    elif k == 'pvin':
                        g.append(dic2['pvintot']-dic['pvintot'])
                    else:
                        g.append(dic2[k])
            y.append([*g])
            dic=S.savedic(dic2)
            i+=1
            dmonth=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[1])
            dday=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[2])
            dyear=int(str(dt.date(year,month,day)+dt.timedelta(days=i)).split('-')[0])
        x,y=np.asarray(x),np.asarray(y)
        elss=ldic['elsold'] - sdic['elsold']
        elbs=ldic['elbought'] - sdic['elbought']
        gabs=ldic['gabought'] - sdic['gabought']
        tlods=ldic['tload'] - sdic['tload']
        S.sumry('year',month,elss,elbs,gabs,tlods)
        return Mplot(x,y,'Values from 01-01-{} until 31-12-{}'.format(year,year),show,S.labels)
                
        
    def sumry(self,typ,month,es,eb,gb,tl):
        S=self
        eurpkwb=float(S.sinks['Electricity Cost from grid (Eur/kWh)'])
        eurpkws=float(S.sinks['Revenue from selling to grid (Eur/kWh)'])
        eurpm=float(S.sinks['Gas cost (Eur/m^3)'])
        tote=float(S.sinks['Electricity Consumption per year (kWh)'])
        gaspd=float(S.sinks['Gas Consumption per year (m^3)'])/float(S.heatdays)
        co2perkwe= 0.4 #https://www.umweltbundesamt.de/presse/pressemitteilungen/bilanz-2019-co2-emissionen-pro-kilowattstunde-strom
        co2permg=2.2 #https://www.researchgate.net/post/What_is_the_environmental_impact_of_1m3_of_natural_gas_used_for_heating
        mn, mx = S.sinks['Heating period (Month - Month)'].split('-')
        dic=self.sum
        if typ == 'month':
            f=float(calendar.monthrange(int(S.initial[0]),month)[0])
            if f>0:
                factor=365/f
            else:
                factor=30
        gfactor=calendar.monthrange(int(S.initial[0]),month)[1] #30#float(S.heatdays)/(12-int(mn)+int(mx))
        if typ == 'day':
            factor=365
            gfactor=1
        if typ == 'year':
            factor=1
            gfactor=float(S.heatdays)
            mn=0
        dic['Electricity cost (Eur)']=eb*eurpkwb
        dic['Autonomy rate el (%)']=max(1-eb/(tl),0)*100
        pvalone=float(S.pv['PV-alone savings (Eur)'])
        if S.general['pv']=='1':
            dic['Money saved el (Eur)']=max((tl-eb)*eurpkwb+es*eurpkws-pvalone,0) #-12116/factor  #MIONTEC
        else:
            dic['Money saved el (Eur)']=max((tl-eb)*eurpkwb+es*eurpkws,0)
        dic['CO2 avoided el (kg)']=max((tl-eb)*co2perkwe,0)
        if month >= int(mn) or month <= int(mx):
#            if gfactor==0:
#                gfactor=1 #Weird April Bug
            totg=gaspd*gfactor
            dic['Gas cost (Eur)']=gb*eurpm
            dic['Autonomy rate g (%)']=max(1-gb/(totg),0)*100
            dic['Money saved g (Eur)']=max((totg-gb)*eurpm,0)
            dic['CO2 avoided g (kg)']=max((totg-gb)*co2permg,0)
        else:
            dic['Gas cost (Eur)']=0
            dic['Autonomy rate g (%)']=100
            dic['Money saved g (Eur)']=0
            dic['CO2 avoided g (kg)']=0
        dic["Total savings (Eur)"]=max(dic['Money saved el (Eur)']+dic['Money saved g (Eur)'],0)
        dic["Total avoided CO2 (kg)"]=max(dic['CO2 avoided g (kg)']+dic['CO2 avoided el (kg)'],0)
        S.sum=dic

    def totsumry(self):
        S=self
        
#        S.tsum['----------']=''
        #Productivity summary
        #Total Solar input
        S.tsum['Total AC electricity produced (MWh)']=S.sim['pvintot']/1000
        #Total Solar el sold to grid
        S.tsum['Total electricity sold to grid (MWh)']=S.sim['elsold']/1000
        #Money made from selling Electricity
        S.tsum['Revenue from sold electricity (Eur)']=float(S.sim['elsold'])*float(S.sinks['Revenue from selling to grid (Eur/kWh)'])
        #Total Hydrogen produced
        S.tsum['Total H2 produced (kg)']=S.sim['toth']
        S.tsum['Capacity Factor EL (%)']=100*(float(S.sim['etime'])/8760)
        S.tsum['Capacity Factor FC (%)']=100*(float(S.sim['ftime'])/8760)
        
        
        #cost of components:
        pcost,ecost,bcost,scost,fcost,pcost=0,0,0,0,0,0
        #PV Installation Cost ??? Guess 500 /m2  ;; https://www.solarchoice.net.au/blog/200kw-solar-pv-systems-compare-prices-and-installer-options/
        #360,000 for 200 kw :: 1 800 E / kW -- 500 eur /m2
        S.tsum['Photovoltaics Cost (Eur)']=0
        if S.general['pv'] == '1' and S.input['Input Type (power (kW) / irradiance (W/m2))']=='irradiance' and S.pv['PV-alone savings (Eur)']=='0':
            pvarea=float(S.pv['Total Area (m2)'])
            pcost=pvarea*500
            S.tsum['Photovoltaics Cost (Eur)']=pcost
        
        #Electrolyzer AEM: 9000 Eur / 2.4 kW = 3750 Eur / kW
        #Electrolyzer PEM: 200,000 Eur / 50 kW = 4000 Eur / kWh
        S.tsum['Electrolyzer Cost (Eur)']=0
        if S.general['elyzer'] == '1':
            kws=float(S.elyzer['Module Power (kW)'])*float(S.elyzer['Number of Modules'])
            if S.elyzer['Type (PEM/AEM)']=='PEM':
                ecost=4000*kws
            else:
                ecost=3750*kws
            S.tsum['Electrolyzer Cost (Eur)']=ecost
        
        #Battery Redox-Flow: 300,000 / 400 kWh = 750 Eur / kwh
        S.tsum['Battery Cost (Eur)']=0
        if S.general['bat']=='1':
            bcap=int(S.bat['Total Capacity  (kWh)'])
            bcost=bcap*750
            S.tsum['Battery Cost (Eur)']=bcost
        
        #H2-storage
        #Prices MH Eur / kg: 12 500 - 22 000
        S.tsum['H2-storage Cost (Eur)']=0
        if S.general['storage']=='1':
            sto=float(S.storage['Total Capacity  (kg)'])
            scost=12500*sto
            S.tsum['H2-storage Cost (Eur)']=scost

        #Fuel Cell
        # No fix price yet, guess around 5,000 Eur / kW AC            
        S.tsum['Fuel Cell Cost (Eur)']=0
        if S.general['fcell']=='1':
            cell=float(S.fcell['Maximum Power (kW)'])
            fcost=cell*5000
            S.tsum['Fuel Cell Cost (Eur)']=fcost
        
        #Total Costs and ROE
        invest=ecost+bcost+scost+fcost+pcost
        S.tsum['Total investment (Eur)']=invest
        eurpkwb=float(S.sinks['Electricity Cost from grid (Eur/kWh)'])
        eurpkws=float(S.sinks['Revenue from selling to grid (Eur/kWh)'])
        eurpm=float(S.sinks['Gas cost (Eur/m^3)'])
        tote=float(S.sinks['Electricity Consumption per year (kWh)'])
        totg=float(S.sinks['Gas Consumption per year (m^3)'])
        totex=tote*eurpkwb+totg*eurpm
        pvalone=float(S.pv['PV-alone savings (Eur)'])
        if S.general['pv']=='1': # and S.input['Input Type (power (kW) / irradiance (W/m2))']=='power':
            totex=totex-pvalone
        S.tsum['Current yearly cost of el & gas (Eur)']=totex
        savings=float(S.sum['Total savings (Eur)'])
        S.tsum['Remaining yearly cost (Eur)']=totex-savings
        if savings!=0 and invest != 0:
            roe=invest/savings
            roi=savings/invest*100
        else:
            roe,roi=0,0
        S.tsum['Return of investment (years)']=(roe)
        S.tsum['Return on investment (%)']=roi
                
        
        
        
        
    def savedic(self,dic):
        tdic={}
        for (key, value) in zip(dic.keys(),dic.values()):
            tdic[key]=value
        return tdic

        
        
class Mplot(Figure):

    def __init__(self,x,y,date,show,labels):
        Figure.__init__(self, figsize=(6, 6), dpi=100)
        ax = self.add_subplot(111)
        S=self
        colors={'pvintot' : '#CDC572', 'onmod' : '#5929E7',\
        'bcharge' : '#FF9A00', 'scharge' : '#1D268C', \
        'elbought' : '#6D706D', 'elsold' : '#249CA0', \
        'gabought' : '#F94052', 'pvin' : '#E7F039' }
        c=0
        for key in show.keys():
        	if show[key]==1 and key!='LOG':
        		ax.plot(x,y[:,c], color=colors[key], label='{}'.format(labels[key]))
        	c+=1
        #ax.plot(x,y[:,2], label='kWh Batterieladung')
        #ax.plot(x,y[:,7], label='kWh PV Produktion')
#        fig.set_size_inches(6,6)
        ax.set_xlabel(show['xaxis'])
        ax.set_ylabel('Values')
        ax.set_title('{}'.format(date))
        ax.tick_params(
	    axis='x', direction='in')
        ax.tick_params(
	        axis='x', which='minor', direction='in')
        ax.tick_params(
	        axis='y', direction='in')
        ax.tick_params(
	        axis='y', which='minor', direction='in')
        ax.tick_params(top=True, right=True)
        ax.tick_params(which='minor', top=True, right=True)
        ax.xaxis.set_minor_locator(AutoMinorLocator()) #FixedLocator(np.arange(-30,30,2))
        ax.yaxis.set_minor_locator(AutoMinorLocator())
        #ax.set_xticks(np.arange(0,mx+10,10))
        #ax.set_yticks(np.arange(0,5000,250))
        #ax.grid()
        ax.legend()
        if show['LOG']==1:
            ax.set_yscale('log')
        #fig.savefig('Fullsim2.pdf')
#        return fig
        


class Optimization:

    def __init__(self,percents=20,roi=20,rounds=500,ityp='percent'):
        self.percent=percents
        self.goalre=roi
        self.rounds=rounds
        self.rnd=0
        self.stp=1
        self.sim=Simulation()
        self.loadar=self.sim.loadarray
        random.seed()
        self.oldre,self.oldsv=self.run()
        self.inre=self.oldre
        self.insv=self.oldsv
        self.failcount=0
        self.etype='A'
        self.ityp=ityp
        self.label,self.last=self.mkarrays()
        self.current=self.last
        self.module=self.getModules()
        
    def mkarrays(self):
        S=self  
        last=[0,0,0,0,0]
        label=[]
        last[0]=float(S.sim.storage['Total Capacity  (kg)'])
        label.append('Total H2 storage Capacity (kg)')
        last[1]=int(S.sim.elyzer['Number of Modules'])
        label.append('# of EL modules')
        last[2]=float(S.sim.fcell['Maximum Power (kW)'])
        label.append('Fuel cell power (kW)')
        last[3]=float(S.sim.bat['Total Capacity  (kWh)'])
        label.append('Battery Capacity (kWh)')
        last[4]=float(S.sim.pv['Total Area (m2)'])
        label.append('Total PV area (m2)')
        return label,last

    def getModules(self):
        S=self
        general=S.sim.general
        module=[]
        if general['storage']=='1':
#            print('H2 storage included')
            module.append(1)
        else:
            module.append(0)
        if general['elyzer']=='1':
            if S.sim.elyzer['Type (PEM/AEM)'] == 'PEM':
                S.last[1]=int(S.sim.elyzer['Module Power (kW)'])
                S.label[1]='EL Module Power'
                S.etype='P'
#            print('Electrolyzer included')
            module.append(1)
        else:
            module.append(0)
        if general['fcell']=='1':
#            print('Fuel cell included')
            module.append(1)
        else:
            module.append(0)
        if general['bat']=='1':
#            print('Battery included')
            module.append(1)
        else:
            module.append(0)
        if S.sim.input['Input Type (power (kW) / irradiance (W/m2))']=='irradiance' and general['pv']=='1':
#            print('PV included')
            module.append(1)
        else:
            module.append(0)
        return module
        
        
    def printall(self):
        S=self
#        print('ROI:',int(S.inre),', Savings:',int(S.insv), '@ START')
#        print('')
#        for i in range(len(S.label)):
#            print(S.label[i],int(S.last[i]))
        return zip(S.label,S.last)
        
    def set(self):
        S=self
        current=S.current
        S.sim.storage['Total Capacity  (kg)']=current[0]
        if S.sim.elyzer['Type (PEM/AEM)'] == 'PEM':
            S.sim.elyzer['Module Power (kW)']=current[1]
        else:
            S.sim.elyzer['Number of Modules']=current[1]
        S.sim.fcell['Maximum Power (kW)']=current[2]
        S.sim.bat['Total Capacity  (kWh)']=current[3]
        S.sim.pv['Total Area (m2)']=current[4]
        
    def vary(self,num):
        S=self
        new,current=[],[]
        last=S.last
        percent=S.percent
        for i in last:
            new.append(i)
        p=random.randint(-1,1)
        if num!=1 or S.sim.elyzer['Type (PEM/AEM)'] == 'PEM':
            if S.ityp=='percent':
                incr=last[num]*percent/100
            else:
                incr=percent
            new[num]=max(last[num]+p*incr,1)
        else:
            new[num]=max(last[num]+p,1)
        #print((last[num]),p*last[num]*percent/100,'->',(new[num]))
        S.current=new
    #    print(new[num],current[num])
        S.set()
    
        
    def run(self):
        S=self
#        S.sim=Simulation()
        S.sim.solar=S.sim.importData()
        S.sim.loadarray=S.loadar
        S.sim.run()
        date=S.sim.final
        elss=float(S.sim.dataset[date]['elsold'])
        elbs=float(S.sim.dataset[date]['elbought'])
        gabs=float(S.sim.dataset[date]['gabought'])
        tlods=float(S.sim.dataset[date]['tload'])
        S.sim.sumry('year',1,elss,elbs,gabs,tlods)
        S.sim.totsumry()
        #return (S.sim.tsum['Return of investment (years)'],S.sim.sum['Total savings (Eur)'])
        return (S.sim.tsum['Return on investment (%)'],S.sim.sum['Total savings (Eur)'])

class GraphPage(tk.Frame):

    def __init__(self, parent):
        tk.Frame.__init__(self, parent)
        self.title_label = tk.Label(self)
        self.title_label.pack()
        self.pack()

    def add_mpl_figure(self, fig):
        self.mpl_canvas = FigureCanvasTkAgg(fig, self)
        self.mpl_canvas.draw()
        self.mpl_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.toolbar = NavigationToolbar2Tk(self.mpl_canvas, self)
        self.toolbar.update()
        self.mpl_canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)


class MPLGraph(Figure):

    def __init__(self):
        Figure.__init__(self, figsize=(5, 5), dpi=100)
        self.plot = self.add_subplot(111)
        self.plot.plot([1, 2, 3, 4, 5, 6, 7], [4, 3, 5, 0, 2, 0, 6])


# MAIN PROGRAM START
root = Tk()
root.title("Simulating H2 Energy Storage System")
root.tk.call('tk', 'scaling', 1)

#Initialization
frame = LabelFrame(root, text='Start Frame', padx=5, pady=5)
cframe = LabelFrame(frame, text='config Frame', padx=5, pady=5)
vframe = LabelFrame(frame, text='Simulation', padx=5, pady=5)
v3frame = LabelFrame(frame, text='Simulation', padx=5, pady=5)
v2frame = LabelFrame(frame, text='Simulation', padx=5, pady=5)
sframe = LabelFrame(frame, text='Simulation', padx=5, pady=5)

modules={}
modules['pv']='Photovoltaics'
modules['general']='General'
modules['elyzer']='Electrolyzer'
modules['bat']='Battery bank'
modules['storage']='Hydrogen storage'
modules['fcell']='Fuel cell'
modules['input']='Solar Input Data'
modules['sinks']='Electricity use / Heating'
modules['opti']='Optimization parameters'


### Main menu bar ###
#Quit
def quit():
    global root
    root.quit()
    root.destroy()

quitbutton = Button(root, text="Quit", command=quit)
quitbutton.grid(row=0,column=0)

#Help
def help():
    global root, frame, confbutton, myimg
    confbutton["state"]=NORMAL
    runbutton["state"]=NORMAL
    optibutton["state"]=NORMAL
    helpbutton["state"]=DISABLED
    frame.grid_forget()
    frame = LabelFrame(root, text='Quickstart Manual', padx=5, pady=5)
    frame.grid(row=1,columnspan=10,padx=5,pady=5)
#    myimg=ImageTk.PhotoImage(Image.open("tk/help.jpg"))
#    mylab=Label(frame, image=myimg, text='gg')
#    mylab.grid(row=0,column=0)
    helptext=['Obtaining Irradiance Data:',' Visit https://maps.nrel.gov/nsrdb-viewer','Pick location under "download data" and include DNI and GHI columns','Download as csv and edit with spreadsheet manipulator', \
    'Make a column and add DNI+GHI together, remove headers and save as csv.', 'Configure column numbers under Configure/Solar Input (A=col 1, B=col 2, ...).','Set input type = irradiance and input datapoint frequency','\n','Configure included modules under Configure/General','Adapt module parameters under Configure/[module]', 'Configure Sinks','Press RUN to run simulation']
    label=[]
    i=0
    for line in helptext:
        label.append(Label(frame, text='{}'.format(line)))
        label[i].grid(row=i)
        i+=1
        
helpbutton = Button(root, text="Help", command=help)
helpbutton.grid(row=0,column=1)
  

#Configuration
def savecfg(module,keys,values):
    global root, frame, cframe,vrs
    with open("config/{}.cfg".format(module), "w") as f:
        for i in range(len(keys)):
            key=keys[i].cget("text").strip()
            if module == 'general':
                value=vrs[i].get()
            else:
                value=values[i].get()
            f.write('%s, %s\n' % (key, value))
    f.close()
    loadcfg(module)

def revertcfg(module):
    global root, frame, cframe
    keys,values=[],[]
    with open("config/{}.cfg.org".format(module), "r") as f:
        for line in f:
            (key, value) = line.split(',')
            values.append(value) 
            keys.append(key)
    f.close()
    with open("config/{}.cfg".format(module), "w") as f:
        for i in range(len(keys)):
            key=keys[i]
            value=values[i]
            #f.writeline("{}, {}".format(key,value))
            f.write('%s, %s' % (key, value))
    f.close()
    loadcfg(module)
    

def loadcfg(module):
    global cframe, frame, modules,vrs
    cframe.grid_forget()
    cframe = LabelFrame(frame, text="{} configuration".format(modules[module]), padx=5, pady=5)
    cframe.grid(row=2,columnspan=10,padx=5,pady=5)
    savebutton=Button(cframe, text='save', command=lambda: savecfg(module,klabel,vlabel)).grid(row=100,column=0)
    revertbutton=Button(cframe, text='defaults', command=lambda: revertcfg(module)).grid(row=100,column=1)
    dic={}
    klabel=[]
    keys=[]
    vlabel=[]
    jlabel=[]
    clabel=[]
    v=0
#    with open("config/{}.cfg".format(module), "r") as f:
    try:
         f=open("config/{}.cfg".format(module), "r")
    except:
        try:
             f=open("config/{}.cfg.org".format(module), "r")
        except:
            newconfig(module)
#            savecfg(module)
            f=open("config/{}.cfg.org".format(module), "r")
    for line in f:
        (key, value) = line.split(',')
        dic[key] = (value.strip('\n').strip())
        keys.append(key)
        if module == 'general':
            vrs[v].set(int(dic[key]))
            u=vrs[v]
            jlabel.append(Label(cframe, text='{}'.format(modules[key])))
            clabel.append(Checkbutton(cframe,variable=u))
#                if vrs[v].get()==1:
#                    clabel[v].select()
            v+=1
        klabel.append(Label(cframe, text=key))
        vlabel.append(Entry(cframe, width=25))
    f.close()
    for i in range(len(klabel)):
            key=keys[i]
            vlabel[i].insert(0,dic[key])
            if module == 'general':
                jlabel[i].grid(row=i,column=0)
                clabel[i].grid(row=i,column=1)
            else:
                klabel[i].grid(row=i,column=0)
                vlabel[i].grid(row=i,column=1)
    

def newconfig(module):
    try:
        os.mkdir('config', 0o666)
    except:
        pass
    cfg={}
    cfg['general']='pv, 1\nbat, 1\nelyzer, 1\nstorage, 1 \nfcell, 1'
    cfg['pv']='Peak Power (kW), 200\nTotal Area (m2), 730\nEfficiency (%), 18\nPV-alone savings (Eur), 15000\n'
    cfg['elyzer']='Type (PEM/AEM), AEM\nModule Power (kW), 2.4\nNumber of Modules, 10\nConversion Rate (kWh/m3), 4.8'
    cfg['bat']='Total Capacity  (kWh), 52\nFull cycle efficiency (%), 85\nInitial Charge (%), 0\n'
    cfg['storage']='Total Capacity  (kg), 30\nCharging Cost (kWh/kg), 0.1\nDischarging Cost (kWh/kg), 0.2\nInitial charge (kg), 0'
    cfg['fcell']='Maximum Power (kW), 6\nConversion Rate (kWh/kg), 21.45'
    cfg['input']='Input Type (power (kW) / irradiance (W/m2)),  irradiance\nDatapoint frequency (per hour),   4\n\
        Year column,  1\nMonth column,  2\nDay column,  3\nHour column,  4\nMinute column,  5\nInput column,  6\nFilename,  ndata.csv'
    cfg['sinks']='Electricity Cost from grid (Eur/kWh),  0.28\nRevenue from selling to grid (Eur/kWh),  0.03\nElectricity Consumption per year (kWh),  71000\n\
        Electricity base load (kW),  4\nGas cost (Eur/m^3),  1.2\nGas Consumption per year (m^3),  20000\nHeating period (Month - Month),  10-4\n\
        max H2 portion in mix (%),  30'
    cfg['opti']='Initial change step, 20\nchange unit (absolute / percent), percent\nPlanned ROI (%), 4\nOptimize PV? (y/n), n\nMax optimization rounds, 1000'
    f=open("config/{}.cfg.org".format(module), "w")
    g=open("config/{}.cfg".format(module), "w")
    f.write(cfg[module])
    g.write(cfg[module])
    f.close()
    g.close()
        
    
def forgetall():
    global frame,cframe,vframe,v2frame,v3frame
    fr=[v3frame,v2frame,vframe,cframe,frame]
    for ame in fr:
        ame.grid_forget()
#    frame.destroy()
            
def config():
    global root,frame,confbutton,vrs,vframe
    #forgetall()
    vframe.grid_forget()
    sframe.grid_forget()
    frame.grid_forget()
    frame = LabelFrame(root, text='Configuration', padx=5, pady=5)
    frame.grid(row=1,columnspan=5,padx=5,pady=5)
    confbutton["state"]=DISABLED
    runbutton["state"]=NORMAL
    optibutton["state"]=NORMAL
    helpbutton["state"]=NORMAL
    
    #General Config Checkbuttons
    vrs=[IntVar(),IntVar(),IntVar(),IntVar(),IntVar()]
    
    #Config Frame Control Buttons 
    c1 = Button(frame, text='General', command= lambda: loadcfg('general'))
    c1.grid(row=0,column=0)
    c2 = Button(frame, text='PV', command= lambda: loadcfg('pv'))
    c2.grid(row=0,column=1)
    c3 = Button(frame, text='Electrolyzer', command= lambda: loadcfg('elyzer'))
    c3.grid(row=0,column=2)
    c4 = Button(frame, text='Battery', command= lambda: loadcfg('bat'))
    c4.grid(row=0,column=3)
    c5 = Button(frame, text='H2-Storage', command= lambda: loadcfg('storage'))
    c5.grid(row=0,column=4)
    c6 = Button(frame, text='Fuel Cell', command= lambda: loadcfg('fcell'))
    c6.grid(row=0,column=5) 
    c7 = Button(frame, text='Solar Input', command=lambda: loadcfg('input'))
    c7.grid(row=0,column=6) 
    c8 = Button(frame, text='Sinks', command=lambda: loadcfg('sinks'))
    c8.grid(row=0,column=7) 
    c9 = Button(frame, text='Optimize', command=lambda: loadcfg('opti'))
    c9.grid(row=0,column=8) 
    
    
confbutton = Button(root, text="Configure", command=config)
confbutton.grid(row=0,column=2)


#Run simulation
def plot(typ,year,month=1,day=1,current=0):
    global root, frame, vframe, v2frame, sim, show
    if typ == 'day':
        show['xaxis']='Hour of the day'
        fig=sim.plotDay(year,month,day,show,current)
    if typ == 'month':
        show['xaxis']='Day of the month'
        fig=sim.plotMonth(year,month,show)
    if typ == 'year':
        show['xaxis']='Day of the year'
        fig=sim.plotYear(year,month,show)
    graph_page = GraphPage(v2frame)
    graph_page.add_mpl_figure(fig)

def getchk():
    global show
    global v9,v10,v11,v12,v13,v14,v15,v16,v17
    show['pvin']=v9.get()
    show['pvintot']=v10.get()
    show['bcharge']=v11.get()
    show['scharge']=v12.get()
    show['elbought']=v13.get()
    show['elsold']=v14.get()
    show['gabought']=v15.get()
    show['onmod']=v16.get()
    show['LOG']=v17.get()
    
def refresh(typ,year,month=1,day=1):
    global root, frame, confbutton, sim, vframe, v2frame, v3frame,sframe, current,show
    global c5,c6,c7,c8
    global v9,v10,v11,v12,v13,v14,v15,v16,v17
    frame.grid_forget()
    #Frames
    frame = LabelFrame(root, text='Simulation', padx=5, pady=5)
    frame.grid(row=1,columnspan=5,padx=5,pady=5)
    vframe = LabelFrame(frame, text='Controls', padx=5, pady=5)
    vframe.grid(row=1,columnspan=5, padx=5,pady=5)
    v2frame = LabelFrame(vframe, text='Viewer', padx=5, pady=5)
    v2frame.grid(row=2,columnspan=5, rowspan = 12)
    v3frame = LabelFrame(vframe, text='Summary', padx=5, pady=5)
    v3frame.grid(row=12,column=5,columnspan=2, rowspan = 2)
    
    #Sim frame buttons
    c1 = Button(frame, text='by Day', command= lambda: refresh('day',year,1,1))
    c1.grid(row=0,column=0)
    c2 = Button(frame, text='by Month', command= lambda: refresh('month',year,1,1))
    c2.grid(row=0,column=1)
    c3 = Button(frame, text='by Year', command= lambda: refresh('year',year,1,1))
    c3.grid(row=0,column=2)
    c4 = Button(frame, text='Summary', command= lambda: refresh('summary',year,1,1))
    c4.grid(row=0,column=3)    
    #Viewer buttons 
    c5 = Button(vframe, text='previous day', command=lambda: prvd(typ,year,month,day))
    c6 = Button(vframe, text='next day', command=lambda: nxtd(typ,year,month,day))
    if typ=='day':
        c5.grid(row=1,column=1)
        c6.grid(row=1,column=2)
    c7 = Button(vframe, text='previous month', command=lambda: prvm(typ,year,month,day))
    c8 = Button(vframe, text='next month', command=lambda: nxtm(typ,year,month,day))
    if typ == 'day' or typ == 'month':
        c7.grid(row=1,column=0)
        c8.grid(row=1,column=3)
    #Config Plot
    c9 = Checkbutton(vframe, text='Current power input AC',variable=v9)
    c9.grid(row=2,column=5)
    c10 = Checkbutton(vframe, text='Total power input AC',variable=v10)
    c10.grid(row=3,column=5)
    c11 = Checkbutton(vframe, text='Battery Charge level',variable=v11)
    c11.grid(row=4,column=5)
    c12 = Checkbutton(vframe, text='Hydrogen Storage level',variable=v12)
    c12.grid(row=5,column=5)
    c13 = Checkbutton(vframe, text='Electricity purchased',variable=v13)
    c13.grid(row=6,column=5)
    c14 = Checkbutton(vframe, text='Electricity sold',variable=v14)
    c14.grid(row=7,column=5)
    c15 = Checkbutton(vframe, text='Gas purchased',variable=v15)
    c15.grid(row=8,column=5)
    c16 = Checkbutton(vframe, text='EL modules on',variable=v16)
    c16.grid(row=9,column=5)
    c17 = Checkbutton(vframe, text='LOG scale',variable=v17)
    c17.grid(row=10,column=5)
    c18=Button(vframe, text='refresh', command=lambda: refresh(typ,year,month,day))
    c18.grid(row=1,column=5)
    
    if typ=='day':
        c1["state"]=DISABLED
        c5["state"]=NORMAL
        c6["state"]=NORMAL
        c2["state"]=NORMAL
        c3["state"]=NORMAL
        c4["state"]=NORMAL
    if typ=='month':
        c2["state"]=DISABLED
        c1["state"]=NORMAL
        c3["state"]=NORMAL
        c4["state"]=NORMAL
    if typ=='year':
        c3["state"]=DISABLED
        c1["state"]=NORMAL
        c2["state"]=NORMAL
        c4["state"]=NORMAL
    dyear=int(str(dt.date(year,month,day)+dt.timedelta(days=current+1)).split('-')[0])
    if dyear != year:
        c6["state"]=DISABLED
    if month==12:
        c8["state"]=DISABLED    
    #Output
    if typ!='summary':
        getchk()
        plot(typ,year,month,day,current)
        prsum()
    else:
        sframe = LabelFrame(frame, text='Summary', padx=5, pady=5)
        sframe.grid(row=1,columnspan=4, padx=5,pady=5)
        nl=plot('year',year,month,day,current)
        vframe.grid_forget()
        prtotsum()

def nxtd(typ,year,month=1,day=1):
    global current
    current+=1
    refresh(typ,year,month,day)
def prvd(typ,year,month=1,day=1):
    global current
    current-=1
    try:
        refresh(typ,year,month,day)
    except:
        current+=1
        refresh(typ,year,month,day)
        
def nxtm(typ,year,month=1,day=1):
    global current
    current=0
    refresh(typ,year,min(12,month+1),day)
def prvm(typ,year,month=1,day=1):
    global current
    current=0
    refresh(typ,year,max(1,month-1),day)

def prsum():
    global vframe, v3frame, sim
    #v3frame.grid_forget()
    dic=sim.sum
    klabel=[]
    vlabel=[]
    for (key, value) in zip(dic.keys(),dic.values()):
        klabel.append(Label(v3frame, text=key))
        vlabel.append(Label(v3frame, text=int(value)))
    for i in range(len(klabel)):
            klabel[i].grid(row=i,column=0)
            vlabel[i].grid(row=i,column=1)



def prtotsum():
    global sframe, sim
    sim.totsumry()
    dic=sim.savedic(sim.sum)
    dic.update(sim.tsum)
    ssframe=[]
    ssname=['Productivity', 'Cost', 'Investments', 'Overall']
    for i in range(4):
        ssframe.append(LabelFrame(sframe, text=ssname[i], padx=5, pady=5))
    ssframe[0].grid(row=1,column=1)
    ssframe[1].grid(row=2,column=1)
    ssframe[2].grid(row=3,column=1)
    ssframe[3].grid(row=4,column=1)
    sskeys=[]
    sskeys.append(['Total AC electricity produced (MWh)','Total electricity sold to grid (MWh)','Total H2 produced (kg)','Capacity Factor EL (%)','Capacity Factor FC (%)',\
    'Autonomy rate el (%)','Autonomy rate g (%)','Total avoided CO2 (kg)'])
    sskeys.append(['Current yearly cost of el & gas (Eur)','Electricity cost (Eur)','Gas cost (Eur)',\
    'Revenue from sold electricity (Eur)','Total savings (Eur)'])
    sskeys.append(['Photovoltaics Cost (Eur)', 'Electrolyzer Cost (Eur)', 'Battery Cost (Eur)', 'H2-storage Cost (Eur)', \
    'Fuel Cell Cost (Eur)', 'Total investment (Eur)'])
    sskeys.append(['Remaining yearly cost (Eur)', 'Return of investment (years)', 'Return on investment (%)'])
#    (['Electricity cost (Eur)', 'Autonomy rate el (%)', 'Money saved el (Eur)', 'CO2 avoided el (kg)', 'Gas cost (Eur)', 'Autonomy rate g (%)', 'Money saved g (Eur)', 'CO2 avoided g (kg)', 'Total savings (Eur)', 'Total avoided CO2 (kg)', 'Total AC electricity produced (MWh)', 'Total electricity sold to grid (MWh)', 'Total H2 produced (kg)', 'Photovoltaics Cost (Eur)', 'Electrolyzer Cost (Eur)', 'Battery Cost (Eur)', 'H2-storage Cost (Eur)', 'Fuel Cell Cost (Eur)', 'Total investment (Eur)', 'Current yearly cost of el & gas (Eur)', 'Remaining yearly cost (Eur)', 'Return of investment (years)', 'Return on investment (%)'])
    klabel=[]
    vlabel=[]
    spc=0
#    print(dic.keys())
    for fr in range(4):
        klabel=[]
        vlabel=[]
        for key in sskeys[fr]:
            try:
                klabel.append(Label(ssframe[fr], text=key))
                val=round(dic[key],1)
                if val >99:
                    val=int(dic[key])
                if val ==0:
                    klabel=klabel[:-1]
                else:
                    vlabel.append(Label(ssframe[fr], text=val))
            except:
                continue
        for i in range(len(klabel)):
            klabel[i].grid(row=i,column=0)
            vlabel[i].grid(row=i,column=1)

#    for (key, value) in zip(dic.keys(),dic.values()):
#        if spc==10 or spc==14 or spc==19:
#            klabel.append(Label(sframe, text='-----'))
#            vlabel.append(Label(sframe, text='-----'))
#        klabel.append(Label(sframe, text=key))
#        vlabel.append(Label(sframe, text=int(value)))
#        spc+=1
    
def run():
    global root, frame, confbutton, sim, vframe, v2frame, current, show
    global v9,v10,v11,v12,v13,v14,v15,v16,v17
    confbutton["state"]=NORMAL
    optibutton["state"]=NORMAL
    helpbutton["state"]=NORMAL
    runbutton["state"]=DISABLED
    frame.grid_forget()
    frame = LabelFrame(root, text='Simulation', padx=5, pady=5)
    vframe = LabelFrame(frame, text='', padx=5, pady=5)
    
    #Prepare Checkboxes
    v9=IntVar()
    v10=IntVar()
    v11=IntVar()
    v12=IntVar()
    v13=IntVar()
    v14=IntVar()
    v15=IntVar()
    v16=IntVar()
    v17=IntVar()
    #Run simulation
    sim=Simulation()
    sim.run()
    current=0
    show=sim.shw
    v9.set(1)
    v12.set(1)
    #v13.set(1)
    v11.set(1)
    show['pvin']=1
    show['bcharge']=1
    show['scharge']=1
    show['xaxis']='Hour of the day'
    refresh('day',*sim.initial)

    
runbutton = Button(root, text="Run", command=run)
runbutton.grid(row=0,column=3)

def optimize():
    global sim,root,frame,confbutton,vrs,vframe
    #forgetall()
    frame.grid_forget()
    vframe.grid_forget()
    sframe.grid_forget()
    cframe.grid_forget()
    frame = LabelFrame(root, text='Optimization', padx=5, pady=5)
    frame.grid(row=1,columnspan=5,padx=5,pady=5)
    optibutton["state"]=DISABLED
    confbutton["state"]=NORMAL
    runbutton["state"]=NORMAL
    helpbutton["state"]=NORMAL
    
    o1frame = LabelFrame(frame, text='Overall', padx=5, pady=5)
    o2frame = LabelFrame(frame, text='Parameters', padx=5, pady=5)
    o1frame.grid(row=1, columnspan=4)
    o2frame.grid(row=2, columnspan=4)
    
    sim=Simulation()
    per=float(sim.opti['Initial change step'])
    gre=float(sim.opti['Planned ROI (%)'])
    rou=float(sim.opti['Max optimization rounds'])
    opv=sim.opti['Optimize PV? (y/n)']
    ityp=sim.opti['change unit (absolute / percent)']
    opt=Optimization(per,gre,rou,ityp)
    if opv == 'n':
        opt.module[4]=0
    if ityp=='percent':
        ityp2='%'
    else:
        ityp2='abs'
    
    def prints():
        c,d=[],[]
#        c.append(Label(o1frame, text='Return of investment (years)'))
        c.append(Label(o1frame, text='Return on investment (%)'))
        d.append(Label(o1frame, text='  {0:2.1f}  '.format(opt.oldre)))
        c.append(Label(o1frame, text='Annual savings (Eur)'))
        d.append(Label(o1frame, text='  {0:2.0f}  '.format(opt.sim.sum['Total savings (Eur)'])))
        c.append(Label(o1frame, text='Current varation step ({})'.format(ityp2)))
        d.append(Label(o1frame, text='  {0:2.0f}  '.format((opt.percent))))
        c.append(Label(o1frame, text='Current round'))
        d.append(Label(o1frame, text='  {}/{}  '.format(opt.rnd,int(opt.rounds))))
        for i in range(len(c)):
            c[i].grid(row=i+1,column=1)
            d[i].grid(row=i+1,column=2, padx=5)
        
    def printp():
        c,d=[],[]
        prnt=opt.printall()
        i=0
        for k,v, in prnt:
            c.append(Label(o2frame, text=k))
            d.append(Label(o2frame, text='  {0:2.1f}  '.format(v))) #round(v,1)))
            if opt.module[i]==1:
                c[i].grid(row=i+1,column=1)
                d[i].grid(row=i+1,column=2, padx=5)
            i+=1
        
        #Extract variables
    re,sv=0,0
    oldre,oldsv=opt.inre,opt.insv
    goalre=opt.goalre
    percent=opt.percent

    
    prints()
    printp()
        
    def start(con=0):
        opt.rnd=0
        opt.stp=1
        re,sv=0,0
        oldre,oldsv=opt.oldre,opt.oldsv
        goalre=opt.goalre
        percent=opt.percent
        rnd=opt.rnd
        while opt.rnd < rou and opt.stp==1:
            opt.sim=Simulation()
            n=random.randint(0,4) #len(last)-1)
            while opt.module[n]==0:
                n=random.randint(0,4) #len(last)-1) 
            opt.rnd+=1
            opt.vary(n)
            m=n
            while opt.module[n]==0 or n==m:
                n=random.randint(0,4) #len(last)-1) 
            opt.vary(n)
            re,sv=opt.run()
            #if (abs(re-oldre)<1 and sv/oldsv>1.05) or (re+.5 < oldre and (sv/oldsv)>.99) or (re <= goalre and sv>oldsv):
            if (re>opt.oldre and re<goalre) or (re>goalre and sv>opt.oldsv):
                opt.oldsv=sv
                opt.oldre=re
                opt.failcount=0
    #            print('ROI:',int(oldre),', Savings:',int(oldsv),',',label[n],':',round(last[n],1),'->',round(current[n],1))
                printp()
                opt.last[n]=opt.current[n]
            else:
                opt.current[n]=opt.last[n]
                opt.failcount+=1
                #print('...',(re),int(sv),label[n],current[n])
            if opt.failcount>np.sum(np.asarray(opt.module))*8:
                opt.failcount=0
                opt.percent=opt.percent/1.5
                if opt.percent <1:
                    stop()
                #print(int(percent),'% change')
            prints()
        stop()
    
    def stop():
        opt.stp=0
        startbutton["state"]=NORMAL
        stopbutton["state"]=DISABLED
        runbutton["state"]=NORMAL
        confbutton["state"]=NORMAL
        helpbutton["state"]=NORMAL
    def start_thread():
        thread = threading.Thread(target=start)
        thread.start()
        startbutton["state"]=DISABLED
        runbutton["state"]=DISABLED
        confbutton["state"]=DISABLED
        helpbutton["state"]=DISABLED
        stopbutton["state"]=NORMAL
   
    startbutton = Button(frame, text="Start", command=start_thread)
    startbutton.grid(row=0,column=1)
    stopbutton = Button(frame, text="stop", command=stop)
    stopbutton.grid(row=0,column=2)
    stopbutton["state"]=DISABLED
        
optibutton = Button(root, text="Optimize", command=optimize)
optibutton.grid(row=0,column=4)

#Program Loop
#Check configuration
config()
for mod in modules:
    loadcfg(mod)
confbutton["state"]=NORMAL
forgetall()

root.mainloop()
