#!/usr/bin/env python3
"""
Demo script showing the enhanced recurring appointment functionality
Perfect for showing Nate how to create his weekly mental health appointments!
"""

import asyncio
import json
from datetime import datetime, timedelta
from friday_memory_system import FridayMemorySystem

async def demo_recurring_appointments():
    """Demo the new recurring appointment features"""
    
    memory_system = FridayMemorySystem()
    
    print("🗓️  Friday Memory System - Recurring Appointments Demo")
    print("=" * 60)
    
    # Example 1: Nate's weekly mental health appointments
    print("\n1️⃣  Creating Nate's weekly mental health appointments")
    print("   (Every Monday at 2:00 PM for 12 weeks)")
    
    # Next Monday at 2 PM
    next_monday = datetime.now() + timedelta(days=(7 - datetime.now().weekday()))
    start_time = next_monday.replace(hour=14, minute=0, second=0, microsecond=0)
    
    mental_health_result = await memory_system.create_appointment(
        title="Mental Health Appointment",
        scheduled_datetime=start_time.isoformat(),
        description="Weekly therapy session with counselor",
        location="Mental Health Clinic",
        recurrence_pattern="weekly",
        recurrence_count=12  # 12 weeks = 3 months
    )
    
    print(f"   ✅ Created {mental_health_result['count']} weekly appointments!")
    print(f"   📅 First appointment: {start_time.strftime('%A, %B %d at %I:%M %p')}")
    
    # Example 2: Daily medication reminders
    print("\n2️⃣  Creating daily medication reminders")
    print("   (Every day at 9:00 AM for 30 days)")
    
    tomorrow_9am = (datetime.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    
    medication_result = await memory_system.create_appointment(
        title="Take Morning Medications",
        scheduled_datetime=tomorrow_9am.isoformat(),
        description="Take daily medications with breakfast",
        recurrence_pattern="daily",
        recurrence_count=30  # 30 days
    )
    
    print(f"   ✅ Created {medication_result['count']} daily medication reminders!")
    
    # Example 3: Monthly doctor visits with end date
    print("\n3️⃣  Creating monthly doctor check-ups")
    print("   (First Friday of each month through the end of year)")
    
    # Find first Friday of next month
    next_month = datetime.now().replace(day=1) + timedelta(days=32)
    next_month = next_month.replace(day=1)
    first_friday = next_month + timedelta(days=(4 - next_month.weekday()) % 7)
    first_friday = first_friday.replace(hour=10, minute=30, second=0, microsecond=0)
    
    end_of_year = datetime(next_month.year, 12, 31).isoformat()
    
    doctor_result = await memory_system.create_appointment(
        title="Monthly Doctor Check-up",
        scheduled_datetime=first_friday.isoformat(),
        description="Regular health monitoring and medication review",
        location="Family Doctor's Office",
        recurrence_pattern="monthly",
        recurrence_end_date=end_of_year
    )
    
    print(f"   ✅ Created {doctor_result['count']} monthly doctor appointments!")
    print(f"   📅 First appointment: {first_friday.strftime('%A, %B %d at %I:%M %p')}")
    
    # Example 4: Single appointment (no recurrence)
    print("\n4️⃣  Creating a one-time appointment")
    
    single_result = await memory_system.create_appointment(
        title="Dentist Cleaning",
        scheduled_datetime=(datetime.now() + timedelta(days=14)).replace(hour=15, minute=30).isoformat(),
        description="6-month dental cleaning and check-up",
        location="Smile Dental Clinic"
    )
    
    print(f"   ✅ Created {single_result['count']} one-time appointment!")
    
    # Summary
    total_appointments = (mental_health_result['count'] + 
                         medication_result['count'] + 
                         doctor_result['count'] + 
                         single_result['count'])
    
    print(f"\n🎉 Demo Complete!")
    print(f"   Created a total of {total_appointments} appointments")
    print(f"   • {mental_health_result['count']} weekly mental health sessions")
    print(f"   • {medication_result['count']} daily medication reminders")
    print(f"   • {doctor_result['count']} monthly doctor visits")
    print(f"   • {single_result['count']} one-time dentist appointment")
    
    print(f"\n💡 How to use:")
    print(f"   Via MCP tools (VS Code, LM Studio, etc.):")
    print(f"   create_appointment(")
    print(f"     title='Weekly Therapy',")
    print(f"     scheduled_datetime='2025-09-29T14:00:00',")
    print(f"     recurrence_pattern='weekly',")
    print(f"     recurrence_count=12")
    print(f"   )")

if __name__ == "__main__":
    asyncio.run(demo_recurring_appointments())