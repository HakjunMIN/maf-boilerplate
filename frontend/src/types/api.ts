export type JobStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface JobCreateRequest {
  query: string
  input_files: string[]
}

export interface SandboxResultResponse {
  stdout: string
  stderr: string
  exit_code: number
  artifacts: string[]
}

export interface JobResponse {
  job_id: string
  status: JobStatus
  query: string
  input_files: string[]
  summary: string | null
  generated_code: string
  sandbox_result: SandboxResultResponse | null
  web_search_results: string[]
  error_message: string | null
}

export interface HealthResponse {
  status: string
  app: string
}