#!/usr/bin/env python3
"""
Enhanced Study Scheduler with User-Friendly Interface
Keeps you ahead of your classes with an intuitive menu system
"""

import csv
import yaml
from datetime import datetime, timedelta
from collections import defaultdict
import argparse
import os
from pathlib import Path
import inquirer
import sys
from typing import List, Dict, Any

class StudyScheduler:
    def __init__(self, csv_file):
        self.csv_file = csv_file
        self.classes = []
        self.subjects = defaultdict(list)
        self.study_plan = {}
        self.load_classes()
        
    def detect_encoding(self):
        """Try to detect the file encoding"""
        encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'windows-1252']
        
        for encoding in encodings:
            try:
                with open(self.csv_file, 'r', encoding=encoding) as f:
                    f.read()
                return encoding
            except UnicodeDecodeError:
                continue
        
        # Default to latin-1 if none work (it rarely fails)
        return 'latin-1'
        
    def load_classes(self):
        """Load classes from CSV file"""
        encoding = self.detect_encoding()
        
        with open(self.csv_file, 'r', encoding=encoding) as f:
            # Skip any empty lines or non-CSV content
            lines = f.readlines()
            # Find the first line that looks like a CSV header
            header_line = None
            for i, line in enumerate(lines):
                if 'Betreff' in line and 'Beginnt am' in line:
                    header_line = i
                    break
            
            if header_line is None:
                raise ValueError("Could not find CSV header in the file")
            
            # Read from the header line onward
            f.seek(0)
            for _ in range(header_line):
                f.readline()
                
            reader = csv.DictReader(f, delimiter=',')
            for row in reader:
                # Skip empty rows
                if not row.get('Betreff') or not row.get('Beginnt am'):
                    continue
                    
                # Parse date and time
                try:
                    start_date = datetime.strptime(row['Beginnt am'], '%d.%m.%Y')
                    start_time = datetime.strptime(row['Beginnt um'], '%H:%M:%S').time()
                    
                    class_info = {
                        'subject': row['Betreff'],
                        'start_date': start_date,
                        'start_time': start_time,
                        'location': row['Ort'],
                        'description': row['Beschreibung']
                    }
                    
                    self.classes.append(class_info)
                    
                    # Group by subject
                    subject_name = class_info['subject'].split('::')[0].strip()
                    self.subjects[subject_name].append(class_info)
                except ValueError as e:
                    print(f"Skipping row due to parsing error: {e}")
                    continue
        
        # Sort classes by date for each subject
        for subject in self.subjects:
            self.subjects[subject].sort(key=lambda x: x['start_date'])
    
    def generate_study_plan(self, days_ahead=2):
        """Generate study plan to stay ahead of classes"""
        plan = {}
        
        for subject, classes in self.subjects.items():
            for i, class_info in enumerate(classes):
                class_date = class_info['start_date']
                study_date = class_date - timedelta(days=days_ahead)
                
                # If study date is in the past, use today
                if study_date < datetime.now():
                    study_date = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
                
                # Format study session
                session = {
                    'subject': subject,
                    'class_date': class_date.strftime('%Y-%m-%d'),
                    'class_time': class_info['start_time'].strftime('%H:%M'),
                    'topic': f"Class {i+1} preparation",
                    'completed': False,
                    'location': class_info['location']
                }
                
                # Add to plan
                date_str = study_date.strftime('%Y-%m-%d')
                if date_str not in plan:
                    plan[date_str] = []
                plan[date_str].append(session)
        
        self.study_plan = plan
        return plan
    
    def save_plan(self, output_file):
        """Save study plan to YAML file"""
        # Add metadata
        full_plan = {
            'metadata': {
                'generated_on': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'subjects': list(self.subjects.keys()),
                'total_classes': sum(len(classes) for classes in self.subjects.values())
            },
            'study_plan': self.study_plan
        }
        
        with open(output_file, 'w') as f:
            yaml.dump(full_plan, f, default_flow_style=False)
        
        print(f"Study plan saved to {output_file}")
    
    def load_plan(self, input_file):
        """Load study plan from YAML file"""
        with open(input_file, 'r') as f:
            data = yaml.safe_load(f)
        
        if 'study_plan' in data:
            self.study_plan = data['study_plan']
        return self.study_plan
    
    def mark_completed_by_class_date(self, class_date_str, subject):
        """Mark a study session as completed by class date"""
        for study_date, sessions in self.study_plan.items():
            for session in sessions:
                if session['class_date'] == class_date_str and session['subject'] == subject:
                    session['completed'] = True
                    print(f"Marked {subject} for class on {class_date_str} as completed")
                    return True
        print(f"Session not found: {subject} for class on {class_date_str}")
        return False
    
    def mark_completed_by_index(self, study_date, index):
        """Mark a study session as completed by index in the study date"""
        if study_date in self.study_plan and 0 <= index < len(self.study_plan[study_date]):
            session = self.study_plan[study_date][index]
            session['completed'] = not session['completed']  # Toggle status
            return True
        return False
    
    def get_weekly_view(self, week_start=None):
        """Get study plan for the week"""
        if not week_start:
            week_start = datetime.now()
        
        # Adjust to start of week (Monday)
        week_start = week_start - timedelta(days=week_start.weekday())
        week_dates = [(week_start + timedelta(days=i)).strftime('%Y-%m-%d') 
                     for i in range(7)]
        
        week_plan = {}
        for date in week_dates:
            if date in self.study_plan:
                week_plan[date] = self.study_plan[date]
        
        return week_plan
    
    def get_progress(self):
        """Calculate progress statistics"""
        total_sessions = 0
        completed_sessions = 0
        subject_progress = {}
        
        for date, sessions in self.study_plan.items():
            for session in sessions:
                total_sessions += 1
                if session['completed']:
                    completed_sessions += 1
                
                subject = session['subject']
                if subject not in subject_progress:
                    subject_progress[subject] = {'total': 0, 'completed': 0}
                
                subject_progress[subject]['total'] += 1
                if session['completed']:
                    subject_progress[subject]['completed'] += 1
        
        return {
            'total_sessions': total_sessions,
            'completed_sessions': completed_sessions,
            'completion_rate': completed_sessions / total_sessions * 100 if total_sessions > 0 else 0,
            'subject_progress': subject_progress
        }
    
    def get_upcoming_study_days(self, limit=10):
        """Get upcoming study days with their sessions"""
        upcoming_days = []
        today = datetime.now().strftime('%Y-%m-%d')
        
        for date in sorted(self.study_plan.keys()):
            if date >= today:
                day_sessions = self.study_plan[date]
                # Format for display
                display_date = datetime.strptime(date, '%Y-%m-%d').strftime('%a, %Y-%m-%d')
                session_count = len(day_sessions)
                completed_count = sum(1 for s in day_sessions if s['completed'])
                
                upcoming_days.append({
                    'date': date,
                    'display': f"{display_date} ({completed_count}/{session_count} completed)",
                    'sessions': day_sessions
                })
                
                if len(upcoming_days) >= limit:
                    break
        
        return upcoming_days
    
    def get_all_subjects(self):
        """Get all unique subjects in the study plan"""
        subjects = set()
        for date, sessions in self.study_plan.items():
            for session in sessions:
                subjects.add(session['subject'])
        return sorted(list(subjects))
    
    def get_sessions_by_subject(self, subject):
        """Get all sessions for a specific subject"""
        sessions = []
        for date, day_sessions in self.study_plan.items():
            for session in day_sessions:
                if session['subject'] == subject:
                    sessions.append({
                        'study_date': date,
                        'session': session
                    })
        return sorted(sessions, key=lambda x: x['session']['class_date'])


class StudySchedulerUI:
    def __init__(self, scheduler, plan_file):
        self.scheduler = scheduler
        self.plan_file = plan_file
    
    def main_menu(self):
        """Display the main menu"""
        while True:
            questions = [
                inquirer.List(
                    'action',
                    message="What would you like to do?",
                    choices=[
                        'View weekly overview',
                        'View upcoming study days',
                        'Mark sessions as complete',
                        'View progress statistics',
                        'View by subject',
                        'Save and exit',
                        'Exit without saving'
                    ],
                ),
            ]
            
            answers = inquirer.prompt(questions)
            action = answers['action']
            
            if action == 'View weekly overview':
                self.view_weekly_overview()
            elif action == 'View upcoming study days':
                self.view_upcoming_study_days()
            elif action == 'Mark sessions as complete':
                self.mark_sessions_complete()
            elif action == 'View progress statistics':
                self.view_progress_statistics()
            elif action == 'View by subject':
                self.view_by_subject()
            elif action == 'Save and exit':
                self.scheduler.save_plan(self.plan_file)
                print("Study plan saved. Goodbye!")
                break
            elif action == 'Exit without saving':
                print("Exiting without saving. Goodbye!")
                break
    
    def view_weekly_overview(self):
        """Display weekly overview"""
        week_plan = self.scheduler.get_weekly_view()
        
        print("\n" + "="*60)
        print("WEEKLY STUDY OVERVIEW")
        print("="*60)
        
        for date, sessions in sorted(week_plan.items()):
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            print(f"\n{date_obj.strftime('%A, %Y-%m-%d')}:")
            print("-" * 40)
            
            for session in sessions:
                status = "✓" if session['completed'] else "◯"
                print(f"  {status} {session['subject']} - {session['topic']}")
                print(f"    Class: {session['class_date']} at {session['class_time']}")
        
        input("\nPress Enter to continue...")
    
    def view_upcoming_study_days(self):
        """Display upcoming study days and allow marking as complete"""
        upcoming_days = self.scheduler.get_upcoming_study_days(limit=14)
        
        if not upcoming_days:
            print("No upcoming study days found.")
            input("\nPress Enter to continue...")
            return
        
        # Create choices for the menu
        day_choices = [day['display'] for day in upcoming_days]
        day_choices.append("Return to main menu")
        
        questions = [
            inquirer.List(
                'selected_day',
                message="Select a day to view details:",
                choices=day_choices,
            ),
        ]
        
        answers = inquirer.prompt(questions)
        selected_day_display = answers['selected_day']
        
        if selected_day_display == "Return to main menu":
            return
        
        # Find the selected day
        selected_day = None
        for day in upcoming_days:
            if day['display'] == selected_day_display:
                selected_day = day
                break
        
        if selected_day:
            self.view_day_details(selected_day)
    
    def view_day_details(self, day):
        """View details of a specific day and allow marking sessions as complete"""
        while True:
            print(f"\n{day['display']}:")
            print("-" * 40)
            
            # Display sessions with numbers
            for i, session in enumerate(day['sessions']):
                status = "✓" if session['completed'] else "◯"
                print(f"{i+1}. {status} {session['subject']} - {session['topic']}")
                print(f"   Class: {session['class_date']} at {session['class_time']}")
                print(f"   Location: {session['location']}")
            
            # Create menu options
            options = [
                f"Toggle completion for session 1-{len(day['sessions'])}",
                "Return to day selection"
            ]
            
            questions = [
                inquirer.List(
                    'action',
                    message="What would you like to do?",
                    choices=options,
                ),
            ]
            
            answers = inquirer.prompt(questions)
            action = answers['action']
            
            if action == "Return to day selection":
                break
            elif action.startswith("Toggle completion for session"):
                self.toggle_session_completion(day)
    
    def toggle_session_completion(self, day):
        """Toggle completion status for a session in the selected day"""
        session_numbers = list(range(1, len(day['sessions']) + 1))
        session_choices = [str(num) for num in session_numbers]
        session_choices.append("Cancel")
        
        questions = [
            inquirer.List(
                'session_num',
                message="Select a session to toggle:",
                choices=session_choices,
            ),
        ]
        
        answers = inquirer.prompt(questions)
        if answers['session_num'] == "Cancel":
            return
        
        session_idx = int(answers['session_num']) - 1
        if 0 <= session_idx < len(day['sessions']):
            self.scheduler.mark_completed_by_index(day['date'], session_idx)
            print(f"Session {answers['session_num']} toggled.")
    
    def mark_sessions_complete(self):
        """Mark sessions as complete by class date and subject"""
        # Get all unique class dates
        class_dates = set()
        for date, sessions in self.scheduler.study_plan.items():
            for session in sessions:
                class_dates.add(session['class_date'])
        
        if not class_dates:
            print("No sessions found in study plan.")
            return
        
        # Create choices for class dates
        date_choices = sorted(list(class_dates))
        date_choices.append("Return to main menu")
        
        questions = [
            inquirer.List(
                'class_date',
                message="Select a class date:",
                choices=date_choices,
            ),
        ]
        
        answers = inquirer.prompt(questions)
        class_date = answers['class_date']
        
        if class_date == "Return to main menu":
            return
        
        # Get subjects for the selected class date
        subjects = set()
        for date, sessions in self.scheduler.study_plan.items():
            for session in sessions:
                if session['class_date'] == class_date:
                    subjects.add(session['subject'])
        
        if not subjects:
            print(f"No sessions found for class date {class_date}.")
            return
        
        # Create choices for subjects
        subject_choices = sorted(list(subjects))
        subject_choices.append("Return to date selection")
        
        questions = [
            inquirer.List(
                'subject',
                message="Select a subject:",
                choices=subject_choices,
            ),
        ]
        
        answers = inquirer.prompt(questions)
        subject = answers['subject']
        
        if subject == "Return to date selection":
            self.mark_sessions_complete()
            return
        
        # Mark the session as complete
        if self.scheduler.mark_completed_by_class_date(class_date, subject):
            input("Press Enter to continue...")
    
    def view_progress_statistics(self):
        """Display progress statistics"""
        progress = self.scheduler.get_progress()
        
        print("\n" + "="*60)
        print("PROGRESS STATISTICS")
        print("="*60)
        
        print(f"\nOverall completion: {progress['completed_sessions']}/{progress['total_sessions']} "
              f"({progress['completion_rate']:.1f}%)")
        
        print("\nSubject breakdown:")
        for subject, stats in progress['subject_progress'].items():
            completion = stats['completed']/stats['total']*100 if stats['total'] > 0 else 0
            print(f"  {subject}: {stats['completed']}/{stats['total']} ({completion:.1f}%)")
        
        # Calculate how far ahead you are for each subject
        print("\nAhead status:")
        for subject, classes in self.scheduler.subjects.items():
            # Find the next upcoming class
            upcoming_classes = [c for c in classes if c['start_date'] > datetime.now()]
            if upcoming_classes:
                next_class = min(upcoming_classes, key=lambda x: x['start_date'])
                days_until = (next_class['start_date'] - datetime.now()).days
                
                # Find how many classes we've prepared for
                prepared_count = 0
                for date, sessions in self.scheduler.study_plan.items():
                    for session in sessions:
                        if session['subject'] == subject and session['completed']:
                            prepared_count += 1
                
                total_count = len(classes)
                print(f"  {subject}: {prepared_count}/{total_count} classes prepared, "
                      f"next class in {days_until} days")
            else:
                print(f"  {subject}: No upcoming classes")
        
        input("\nPress Enter to continue...")
    
    def view_by_subject(self):
        """View study sessions organized by subject"""
        subjects = self.scheduler.get_all_subjects()
        
        if not subjects:
            print("No subjects found in study plan.")
            return
        
        # Create choices for subjects
        subject_choices = subjects
        subject_choices.append("Return to main menu")
        
        questions = [
            inquirer.List(
                'subject',
                message="Select a subject:",
                choices=subject_choices,
            ),
        ]
        
        answers = inquirer.prompt(questions)
        subject = answers['subject']
        
        if subject == "Return to main menu":
            return
        
        # Get sessions for the selected subject
        sessions = self.scheduler.get_sessions_by_subject(subject)
        
        print(f"\nStudy sessions for {subject}:")
        print("="*60)
        
        for session_info in sessions:
            session = session_info['session']
            status = "✓" if session['completed'] else "◯"
            print(f"{status} Study on {session_info['study_date']} for class on {session['class_date']}")
            print(f"   Topic: {session['topic']}")
            print(f"   Location: {session['location']}")
            print()
        
        input("\nPress Enter to continue...")


def main():
    parser = argparse.ArgumentParser(description='Study Scheduler for Electrical Engineering')
    parser.add_argument('--csv', default='classes.csv', help='Input CSV file with class schedule')
    parser.add_argument('--output', default='study_plan.yaml', help='Output YAML file for study plan')
    parser.add_argument('--days-ahead', type=int, default=2, help='How many days to study ahead of class')
    parser.add_argument('--ui', action='store_true', help='Launch interactive user interface')
    
    args = parser.parse_args()
    
    # Initialize scheduler
    scheduler = StudyScheduler(args.csv)
    
    # Check if plan already exists
    if os.path.exists(args.output):
        scheduler.load_plan(args.output)
    else:
        scheduler.generate_study_plan(args.days_ahead)
        scheduler.save_plan(args.output)
    
    # Launch UI if requested
    if args.ui:
        ui = StudySchedulerUI(scheduler, args.output)
        ui.main_menu()
    else:
        # Fall back to command-line interface
        print("Study plan loaded. Use --ui flag for interactive interface.")
        print(f"Total sessions: {sum(len(sessions) for sessions in scheduler.study_plan.values())}")
        print("Run with --ui for a more user-friendly experience.")

if __name__ == '__main__':
    main()
