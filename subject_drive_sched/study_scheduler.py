#!/usr/bin/env python3
"""
Study Scheduler for Electrical Engineering Student
Keeps you ahead of your classes with smart scheduling
"""

import csv
import yaml
from datetime import datetime, timedelta
from collections import defaultdict
import argparse
import os
from pathlib import Path

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
    
    def mark_completed(self, date_str, subject):
        """Mark a study session as completed"""
        if date_str in self.study_plan:
            for session in self.study_plan[date_str]:
                if session['subject'] == subject:
                    session['completed'] = True
                    print(f"Marked {subject} on {date_str} as completed")
                    return True
        print(f"Session not found: {subject} on {date_str}")
        return False
    
    def get_weekly_view(self, week_start=None):
        """Get study plan for the week"""
        if not week_start:
            week_start = datetime.now()
        
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
    
    def print_weekly_overview(self):
        """Print a formatted weekly overview"""
        week_plan = self.get_weekly_view()
        progress = self.get_progress()
        
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
        
        print("\n" + "="*60)
        print("OVERALL PROGRESS:")
        print(f"Completed: {progress['completed_sessions']}/{progress['total_sessions']} "
              f"({progress['completion_rate']:.1f}%)")
        
        print("\nSUBJECT BREAKDOWN:")
        for subject, stats in progress['subject_progress'].items():
            completion = stats['completed']/stats['total']*100 if stats['total'] > 0 else 0
            print(f"  {subject}: {stats['completed']}/{stats['total']} ({completion:.1f}%)")
        
        # Calculate how far ahead you are for each subject
        print("\nAHEAD STATUS:")
        for subject, classes in self.subjects.items():
            # Find the next upcoming class
            upcoming_classes = [c for c in classes if c['start_date'] > datetime.now()]
            if upcoming_classes:
                next_class = min(upcoming_classes, key=lambda x: x['start_date'])
                days_until = (next_class['start_date'] - datetime.now()).days
                
                # Find how many classes we've prepared for
                prepared_count = 0
                for date, sessions in self.study_plan.items():
                    for session in sessions:
                        if session['subject'] == subject and session['completed']:
                            prepared_count += 1
                
                total_count = len(classes)
                print(f"  {subject}: {prepared_count}/{total_count} classes prepared, "
                      f"next class in {days_until} days")
            else:
                print(f"  {subject}: No upcoming classes")

def main():
    parser = argparse.ArgumentParser(description='Study Scheduler for Electrical Engineering')
    parser.add_argument('--csv', default='classes.csv', help='Input CSV file with class schedule')
    parser.add_argument('--output', default='study_plan.yaml', help='Output YAML file for study plan')
    parser.add_argument('--days-ahead', type=int, default=2, help='How many days to study ahead of class')
    parser.add_argument('--view-week', action='store_true', help='View weekly study plan')
    parser.add_argument('--mark-completed', nargs=2, metavar=('DATE', 'SUBJECT'), 
                       help='Mark a study session as completed (date format: YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    # Initialize scheduler
    scheduler = StudyScheduler(args.csv)
    
    # Check if plan already exists
    if os.path.exists(args.output):
        scheduler.load_plan(args.output)
    else:
        scheduler.generate_study_plan(args.days_ahead)
        scheduler.save_plan(args.output)
    
    # Handle commands
    if args.mark_completed:
        date_str, subject = args.mark_completed
        scheduler.mark_completed(date_str, subject)
        scheduler.save_plan(args.output)
    
    if args.view_week:
        scheduler.print_weekly_overview()

if __name__ == '__main__':
    main()
