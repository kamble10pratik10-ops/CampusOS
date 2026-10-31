export type Role = 'principal' | 'hod' | 'exam_cell';

export interface User {
  id: string;
  email: string;
  role: Role;
  department_id: string | null;
  is_active: boolean;
  created_at: string;
}

export interface ConflictSummary {
  rule_id: string;
  description: string;
  count: number;
  note: string;
}

export interface WorkloadSummary {
  avg_hours_this_week: number;
  max_hours_this_week: number;
  min_hours_this_week: number;
  overloaded_count: number;
}

export interface RecentDecision {
  id: string;
  scenario_summary: string;
  decision_status: 'simulation' | 'approved' | 'rejected';
  created_at: string;
  created_by_email: string;
}

export interface DashboardData {
  total_faculty: number;
  total_courses: number;
  total_sections: number;
  total_rooms: number;
  total_timetable_entries: number;
  demo_today: string;
  faculty_on_leave_today: number;
  faculty_available_today: number;
  occurrences_today: number;
  occurrences_this_week: number;
  conflict_count: number;
  conflicts_summary: ConflictSummary[];
  workload_summary: WorkloadSummary;
  recent_decisions: RecentDecision[];
  data_label: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  milestone: string;
  data_label: string;
}

