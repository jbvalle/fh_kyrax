#!/usr/bin/env python3
"""
Enhanced Study Scheduler with Balanced Daily Schedule
Ensures no empty days in your study plan
Supports explicit reschedule that skips already-completed sessions
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
import math


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

        return 'latin-1'

    def load_classes(self):
        """Load classes from CSV file"""
        encoding = self.detect_encoding()

        with open(self.csv_file, 'r', encoding=encoding) as f:
            lines = f.readlines()
            header_line = None
            for i, line in enumerate(lines):
                # CSV header expected to contain these German columns from exported calendar
                if 'Betreff' in line and 'Beginnt am' in line:
                    header_line = i
                    break

            if header_line is None:
                raise ValueError("Could not find CSV header in the file")

            f.seek(0)
            for _ in range(header_line):
                f.readline()

            reader = csv.DictReader(f, delimiter=',')
            for row in reader:
                if not row.get('Betreff') or not row.get('Beginnt am'):
                    continue

                try:
                    start_date = datetime.strptime(row['Beginnt am'], '%d.%m.%Y')
                    start_time = datetime.strptime(row['Beginnt um'], '%H:%M:%S').time()

                    class_info = {
                        'subject': row['Betreff'],
                        'start_date': start_date,
                        'start_time': start_time,
                        'location': row.get('Ort', ''),
                        'description': row.get('Beschreibung', '')
                    }

                    self.classes.append(class_info)

                    subject_name = class_info['subject'].split('::')[0].strip()
                    self.subjects[subject_name].append(class_info)
                except ValueError as e:
                    print(f"Skipping row due to parsing error: {e}")
                    continue

        for subject in self.subjects:
            self.subjects[subject].sort(key=lambda x: x['start_date'])

    def generate_balanced_study_plan(self, days_ahead=2, skip_completed=False):
        """
        Generate a study plan with no empty days.
        If skip_completed is True, sessions already marked completed in self.study_plan are omitted,
        and remaining sessions are scheduled consecutively starting today (so you can push ahead).
        Otherwise, sessions are scheduled consecutively starting at the earliest desired study date.
        """
        # Preserve completed sessions from existing plan
        completed_sessions = {}
        if skip_completed and self.study_plan:
            for date, sessions in self.study_plan.items():
                for session in sessions:
                    if session.get('completed'):
                        subject = session['subject']
                        class_date = session['class_date']
                        if (subject, class_date) not in completed_sessions:
                            completed_sessions[(subject, class_date)] = session

        # Build all candidate sessions with desired study date metadata
        all_sessions = []
        today_dt = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)

        for subject, classes in self.subjects.items():
            for i, class_info in enumerate(classes):
                class_date = class_info['start_date']
                desired_study_dt = class_date - timedelta(days=days_ahead)

                # If desired study date is in the past, prefer today at 06:00
                if desired_study_dt < datetime.now():
                    desired_study_dt = today_dt

                # Check if this session was already completed
                session_key = (subject, class_date.strftime('%Y-%m-%d'))
                if session_key in completed_sessions:
                    # Keep the completed session as is
                    all_sessions.append(completed_sessions[session_key])
                    continue

                session = {
                    'subject': subject,
                    'class_date': class_date.strftime('%Y-%m-%d'),
                    'class_time': class_info['start_time'].strftime('%H:%M'),
                    'topic': f"Class {i+1} preparation",
                    'completed': False,
                    'location': class_info.get('location', ''),
                    'desired_study_dt': desired_study_dt
                }
                all_sessions.append(session)

        # Sort by class_date to maintain priority
        all_sessions.sort(key=lambda x: x['class_date'])

        if not all_sessions:
            # nothing to schedule
            self.study_plan = {}
            return {}

        total_sessions = len(all_sessions)

        # Decide start_date for scheduling:
        # - If skip_completed is True (rescheduling because user is ahead), start today
        # - Else, start at the earliest desired study date among sessions
        if skip_completed:
            start_date = today_dt.date()
        else:
            earliest_desired = min(s['desired_study_dt'] for s in all_sessions)
            start_date = earliest_desired.date()

        # We'll schedule sessions on consecutive days starting from start_date,
        # placing one session per day (you can extend to more per day if desired).
        # This guarantees there are no empty days in the schedule.
        balanced_plan = {}
        current_date = datetime.combine(start_date, datetime.min.time())
        session_index = 0

        while session_index < total_sessions:
            date_str = current_date.strftime('%Y-%m-%d')

            # Skip already completed sessions when scheduling
            if all_sessions[session_index].get('completed'):
                session_index += 1
                continue

            # At least one session per day (you may extend to multiple per day by changing chunk size)
            sessions_for_day = [all_sessions[session_index]]
            session_index += 1

            balanced_plan[date_str] = sessions_for_day
            current_date += timedelta(days=1)

        # Add completed sessions back to the plan
        for session in completed_sessions.values():
            # Find the original date for completed sessions
            for date, sessions in self.study_plan.items():
                if session in sessions:
                    if date not in balanced_plan:
                        balanced_plan[date] = []
                    balanced_plan[date].append(session)
                    break

        self.study_plan = balanced_plan
        return balanced_plan

    def save_plan(self, output_file):
        full_plan = {
            'metadata': {
                'generated_on': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'subjects': list(self.subjects.keys()),
                'total_classes': sum(len(classes) for classes in self.subjects.values())
            },
            'study_plan': self.study_plan
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(full_plan, f, default_flow_style=False, allow_unicode=True)

        print(f"Study plan saved to {output_file}")

    def load_plan(self, input_file):
        with open(input_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not data:
            self.study_plan = {}
            return self.study_plan

        # The YAML layout stores metadata and study_plan
        if 'study_plan' in data:
            self.study_plan = data['study_plan'] or {}
        else:
            # Backwards compatibility: assume whole file is a plain study_plan dict
            self.study_plan = data or {}
        return self.study_plan

    def mark_completed_by_class_date(self, class_date_str, subject):
        for study_date, sessions in self.study_plan.items():
            for session in sessions:
                if session['class_date'] == class_date_str and session['subject'] == subject:
                    session['completed'] = True
                    print(f"Marked {subject} for class on {class_date_str} as completed")
                    return True
        print(f"Session not found: {subject} for class on {class_date_str}")
        return False

    def mark_completed_by_index(self, study_date, index):
        if study_date in self.study_plan and 0 <= index < len(self.study_plan[study_date]):
            session = self.study_plan[study_date][index]
            session['completed'] = not session.get('completed', False)
            return True
        return False

    def get_weekly_view(self, week_start=None):
        if not week_start:
            week_start = datetime.now()

        week_start = week_start - timedelta(days=week_start.weekday())
        week_dates = [(week_start + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]

        week_plan = {}
        for date in week_dates:
            if date in self.study_plan:
                week_plan[date] = self.study_plan[date]

        return week_plan

    def get_progress(self):
        total_sessions = 0
        completed_sessions = 0
        subject_progress = {}

        for date, sessions in self.study_plan.items():
            for session in sessions:
                total_sessions += 1
                if session.get('completed'):
                    completed_sessions += 1

                subject = session['subject']
                if subject not in subject_progress:
                    subject_progress[subject] = {'total': 0, 'completed': 0}

                subject_progress[subject]['total'] += 1
                if session.get('completed'):
                    subject_progress[subject]['completed'] += 1

        return {
            'total_sessions': total_sessions,
            'completed_sessions': completed_sessions,
            'completion_rate': completed_sessions / total_sessions * 100 if total_sessions > 0 else 0,
            'subject_progress': subject_progress
        }

    def get_upcoming_study_days(self, limit=10):
        upcoming_days = []
        today = datetime.now().strftime('%Y-%m-%d')

        for date in sorted(self.study_plan.keys()):
            if date >= today:
                day_sessions = self.study_plan[date]
                display_date = datetime.strptime(date, '%Y-%m-%d').strftime('%a, %Y-%m-%d')
                session_count = len(day_sessions)
                completed_count = sum(1 for s in day_sessions if s.get('completed'))

                upcoming_days.append({
                    'date': date,
                    'display': f"{display_date} ({completed_count}/{session_count} completed)",
                    'sessions': day_sessions
                })

                if len(upcoming_days) >= limit:
                    break

        return upcoming_days

    def get_all_subjects(self):
        subjects = set()
        for date, sessions in self.study_plan.items():
            for session in sessions:
                subjects.add(session['subject'])
        return sorted(list(subjects))

    def get_sessions_by_subject(self, subject):
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
                        'Reschedule (skip completed)',
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
            elif action == 'Reschedule (skip completed)':
                # regenerate schedule skipping already completed sessions
                self.scheduler.generate_balanced_study_plan(skip_completed=True)
                self.scheduler.save_plan(self.plan_file)
                print("Study plan regenerated, skipping completed sessions.")
            elif action == 'Save and exit':
                self.scheduler.save_plan(self.plan_file)
                print("Study plan saved. Goodbye!")
                break
            elif action == 'Exit without saving':
                print("Exiting without saving. Goodbye!")
                break

    def view_weekly_overview(self):
        week_plan = self.scheduler.get_weekly_view()

        print("\n" + "=" * 60)
        print("WEEKLY STUDY OVERVIEW")
        print("=" * 60)

        for date, sessions in sorted(week_plan.items()):
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            print(f"\n{date_obj.strftime('%A, %Y-%m-%d')}:")
            print("-" * 40)

            for session in sessions:
                status = "✓" if session.get('completed') else "◯"
                print(f"  {status} {session['subject']} - {session['topic']}")
                print(f"    Class: {session['class_date']} at {session['class_time']}")

        input("\nPress Enter to continue...")

    def view_upcoming_study_days(self):
        upcoming_days = self.scheduler.get_upcoming_study_days(limit=14)

        if not upcoming_days:
            print("No upcoming study days found.")
            input("\nPress Enter to continue...")
            return

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

        selected_day = None
        for day in upcoming_days:
            if day['display'] == selected_day_display:
                selected_day = day
                break

        if selected_day:
            self.view_day_details(selected_day)

    def view_day_details(self, day):
        while True:
            print(f"\n{day['display']}:")
            print("-" * 40)

            for i, session in enumerate(day['sessions']):
                status = "✓" if session.get('completed') else "◯"
                print(f"{i+1}. {status} {session['subject']} - {session['topic']}")
                print(f"   Class: {session['class_date']} at {session['class_time']}")
                print(f"   Location: {session.get('location', '')}")

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
        class_dates = set()
        for date, sessions in self.scheduler.study_plan.items():
            for session in sessions:
                class_dates.add(session['class_date'])

        if not class_dates:
            print("No sessions found in study plan.")
            return

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

        subjects = set()
        for date, sessions in self.scheduler.study_plan.items():
            for session in sessions:
                if session['class_date'] == class_date:
                    subjects.add(session['subject'])

        if not subjects:
            print(f"No sessions found for class date {class_date}.")
            return

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

        if self.scheduler.mark_completed_by_class_date(class_date, subject):
            input("Press Enter to continue...")

    def view_progress_statistics(self):
        progress = self.scheduler.get_progress()

        print("\n" + "=" * 60)
        print("PROGRESS STATISTICS")
        print("=" * 60)

        print(f"\nOverall completion: {progress['completed_sessions']}/{progress['total_sessions']} "
              f"({progress['completion_rate']:.1f}%)")

        print("\nSubject breakdown:")
        for subject, stats in progress['subject_progress'].items():
            completion = stats['completed'] / stats['total'] * 100 if stats['total'] > 0 else 0
            print(f"  {subject}: {stats['completed']}/{stats['total']} ({completion:.1f}%)")

        print("\nAhead status:")
        for subject, classes in self.scheduler.subjects.items():
            upcoming_classes = [c for c in classes if c['start_date'] > datetime.now()]
            if upcoming_classes:
                next_class = min(upcoming_classes, key=lambda x: x['start_date'])
                days_until = (next_class['start_date'] - datetime.now()).days

                prepared_count = 0
                for date, sessions in self.scheduler.study_plan.items():
                    for session in sessions:
                        if session['subject'] == subject and session.get('completed'):
                            prepared_count += 1

                total_count = len(classes)
                print(f"  {subject}: {prepared_count}/{total_count} classes prepared, "
                      f"next class in {days_until} days")
            else:
                print(f"  {subject}: No upcoming classes")

        input("\nPress Enter to continue...")

    def view_by_subject(self):
        subjects = self.scheduler.get_all_subjects()

        if not subjects:
            print("No subjects found in study plan.")
            return

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

        sessions = self.scheduler.get_sessions_by_subject(subject)

        print(f"\nStudy sessions for {subject}:")
        print("=" * 60)

        for session_info in sessions:
            session = session_info['session']
            status = "✓" if session.get('completed') else "◯"
            print(f"{status} Study on {session_info['study_date']} for class on {session['class_date']}")
            print(f"   Topic: {session['topic']}")
            print(f"   Location: {session.get('location', '')}")
            print()

        input("\nPress Enter to continue...")


def main():
    parser = argparse.ArgumentParser(description='Study Scheduler for Electrical Engineering')
    parser.add_argument('--csv', default='/home/kyrax/personal/coding/000_fh_kyrax/subject_drive_sched/classes.csv', help='Input CSV file with class schedule')
    parser.add_argument('--output', default='/home/kyrax/personal/coding/000_fh_kyrax/subject_drive_sched/study_plan.yaml', help='Output YAML file for study plan')
    parser.add_argument('--days-ahead', type=int, default=2, help='How many days to study ahead of class')
    parser.add_argument('--ui', action='store_true', help='Launch interactive user interface')
    parser.add_argument('--reschedule', action='store_true',
                        help='Regenerate schedule skipping already completed sessions (runs immediately)')

    args = parser.parse_args()

    scheduler = StudyScheduler(args.csv)

    # If a plan exists, load it (so we can preserve completed flags)
    if os.path.exists(args.output):
        scheduler.load_plan(args.output)
        print(f"Loaded existing plan: {args.output}")
    else:
        # No plan yet — generate once and save
        scheduler.generate_balanced_study_plan(days_ahead=args.days_ahead, skip_completed=False)
        scheduler.save_plan(args.output)

    # If user requested immediate reschedule from CLI, do it now.
    if args.reschedule:
        scheduler.generate_balanced_study_plan(days_ahead=args.days_ahead, skip_completed=True)
        scheduler.save_plan(args.output)
        print("Rescheduled and saved (skipping completed sessions).")

    # Launch UI if requested
    if args.ui:
        ui = StudySchedulerUI(scheduler, args.output)
        ui.main_menu()
    else:
        print("Study plan loaded. Use --ui flag for interactive interface.")
        print(f"Total sessions: {sum(len(sessions) for sessions in scheduler.study_plan.values())}")
        print("Run with --reschedule to re-generate schedule skipping completed sessions.")


if __name__ == '__main__':
    main()
