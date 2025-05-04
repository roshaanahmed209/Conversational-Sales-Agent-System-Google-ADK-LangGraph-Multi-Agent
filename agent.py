from flask import Flask, render_template, request, redirect, url_for
import csv
import os
from datetime import datetime
from threading import Thread
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from adktools import discover_adk_tools
import time


AGENT_MODEL = LiteLlm(model="groq/llama3-8b-8192")


root_agent = Agent(
    name="sales_agent",
    model=AGENT_MODEL,
    description="Sales agent to collect lead information",
    instruction="""You are a helpful sales assistant. Your task is to collect information 
    from leads, including age, country, and product interest...

    You will be given a lead's information and you need to collect the following information:
    - Name
    - Age
    - Country
    - Product Interest
    - Status        
    

    here is an example on how it should be done: THIS IS AN EXAMPLE ONLY DO NOT BRING THIS INFORMATION IN ANY OTHER CONVERSATION
    Agent: "Great! Let’s review the details you’ve provided:

    Your name: Faizan
    Age: 56
    Country: Pakistan
    Product interest: Mobile phone

    Please confirm if the above details are correct by typing 'confirm'."

    the last message should be like this after asking for interest.

    this is an example i want this so i can fill out my csv file. 
    also if the details are not confirmed or not complete it ask the user to fill
    the complete details

    also act as a chat bot and not only strictly restricted to filling out this form    


    """,
    tools=discover_adk_tools([])
)