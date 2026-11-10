export type Role = 'principal' | 'hod' | 'exam_cell';

export interface User {
  id: string;
  email: string;
  role: Role;
  department_id: string | null;
  is_active: boolean;
  created_at: string;
}

export interface DepartmentPublic {
  id: string;
  code: string;
  name: string;
}

export interface FacultyPublic {
  id: string;
  name: string;
  employee_code: string;
  department_id: string;
  department_name: string;
  department_code: string;
  weekly_max_hours: number;
  is_active: boolean;
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

export interface AssignmentProposal {
  occurrence_id: string;
  occurrence_date: string;
  period_id: string;
  period_label: string;
  start_time: string;
  end_time: string;
  course_id: string;
  course_code: string;
  course_name: string;
  section_id: string;
  section_name: string;
  room_id: string;
  room_name: string;
  original_faculty_id: string;
  original_faculty_name: string;
  assigned_faculty_id: string | null;
  assigned_faculty_name: string | null;
  score_breakdown: Record<string, number>;
  total_score: number;
  is_covered: boolean;
}

export interface OptimizationPlan {
  plan_id: string;
  plan_name: string;
  plan_description: string;
  assignments: AssignmentProposal[];
  uncovered_assignments: AssignmentProposal[];
  covered_occurrences: number;
  total_occurrences: number;
  coverage_percentage: number;
  overall_score: number;
  is_valid: boolean;
  solver_status: string;
  score_breakdown: Record<string, number>;
}

export interface CriticIssue {
  issue_code: string;
  severity: 'error' | 'warning' | 'info';
  message: string;
  details: Record<string, any>;
}

export interface CriticResult {
  status: 'feasible_complete' | 'feasible_partial' | 'infeasible' | 'validation_failed' | 'insufficient_data';
  is_approved: boolean;
  issues: CriticIssue[];
  claims_verified: boolean;
  new_hard_violations_count: number;
  resolved_violations_count: number;
  summary: string;
}

export interface StateDiff {
  total_affected_occurrences: number;
  overridden_occurrences_count: number;
  uncovered_occurrences_count: number;
  existing_violations: any[];
  resolved_violations: any[];
  new_violations: any[];
  remaining_violations: any[];
  faculty_workload_shifts: Array<{
    faculty_id: string;
    faculty_name: string;
    before_hours: number;
    after_hours: number;
    delta_hours: number;
  }>;
}

export interface EvidenceRef {
  ref_type: string;
  ref_id: string | null;
  description: string;
}

export interface SimulationRequest {
  faculty_id?: string;
  start_date?: string;
  end_date?: string;
  occurrence_ids?: string[];
  max_alternatives?: number;
  selected_alternative_index?: number;
  scenario_name?: string;
}

export interface SimulationResponse {
  decision_id: string;
  scenario_summary: string;
  scenario_parameters: Record<string, any>;
  critic_status: string;
  affected_occurrences_count: number;
  affected_occurrences: AssignmentProposal[];
  baseline_conflicts_count: number;
  baseline_violations: any[];
  alternatives: OptimizationPlan[];
  selected_plan: OptimizationPlan;
  baseline_greedy_plan?: OptimizationPlan;
  diff: StateDiff;
  critic_result: CriticResult;
  evidence_refs: EvidenceRef[];
  limitations: string[];
  solver_status: string;
  llm_status: string;
  created_at: string;
  created_by_email: string;
  decision_status: 'simulation' | 'approved' | 'rejected';
  data_label: string;
}

export interface AuditListItem {
  id: string;
  scenario_summary: string;
  decision_status: 'simulation' | 'approved' | 'rejected';
  critic_status: string;
  coverage_percentage: number;
  total_affected: number;
  created_at: string;
  created_by_email: string;
  runtime_ms: number;
}

export interface CandidateEligibility {
  faculty_id: string;
  faculty_name: string;
  employee_code: string;
  is_eligible: boolean;
  is_same_department: boolean;
  has_subject_expertise: boolean;
  preference_score: number;
  current_week_hours: number;
  weekly_max_hours: number;
  rejection_reasons: Array<{
    reason_code: string;
    rule_id: string;
    message: string;
    details: Record<string, any>;
  }>;
}

export interface OccurrenceEligibility {
  occurrence_id: string;
  occurrence_date: string;
  course_code: string;
  course_name: string;
  section_name: string;
  original_faculty_name: string;
  period_label: string;
  room_name: string;
  eligible_candidates: CandidateEligibility[];
  ineligible_candidates: CandidateEligibility[];
  total_candidates_evaluated: number;
  eligible_count: number;
  ineligible_count: number;
}

export interface ParsedIntent {
  intent_type: 'leave_simulation' | 'check_conflicts' | 'check_workload' | 'clarification_needed' | 'general_query';
  faculty_name_or_code?: string | null;
  faculty_id?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  department_code?: string | null;
  department_id?: string | null;
  max_alternatives: number;
  confidence: number;
  missing_fields: string[];
  clarification_prompt?: string | null;
  raw_query: string;
}

export interface QueryRequest {
  query: string;
  context?: Record<string, any> | null;
}

export interface QueryResponse {
  query: string;
  parsed_intent: ParsedIntent;
  explanation: string;
  simulation?: SimulationResponse | null;
  conflicts?: any | null;
  workload?: any | null;
  llm_provider: string;
  llm_model?: string | null;
  llm_status: string;
  data_label: string;
}
