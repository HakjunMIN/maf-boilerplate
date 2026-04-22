import { useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'

import type { JobCreateRequest } from '../types/api'

interface JobFormProps {
  onSubmit: (payload: JobCreateRequest) => Promise<void>
  disabled: boolean
}

export function JobForm({ onSubmit, disabled }: JobFormProps) {
  const [query, setQuery] = useState('')
  const [fileDraft, setFileDraft] = useState('')
  const [inputFiles, setInputFiles] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  const addInputFile = () => {
    const value = fileDraft.trim()
    if (!value) {
      return
    }
    if (!inputFiles.includes(value)) {
      setInputFiles((current) => [...current, value])
    }
    setFileDraft('')
  }

  const removeInputFile = (filePath: string) => {
    setInputFiles((current) => current.filter((item) => item !== filePath))
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      addInputFile()
    }
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    const trimmedQuery = query.trim()
    const trimmedDraft = fileDraft.trim()
    const nextFiles = trimmedDraft && !inputFiles.includes(trimmedDraft)
      ? [...inputFiles, trimmedDraft]
      : inputFiles

    if (!trimmedQuery) {
      setError('Query is required.')
      return
    }

    setError(null)
    setFileDraft('')

    await onSubmit({
      query: trimmedQuery,
      input_files: nextFiles,
    })
  }

  return (
    <section className="panel panel--form">
      <div className="section-head">
        <div>
          <p className="section-kicker">Dispatch</p>
          <h2>Create analysis job</h2>
        </div>
        <p className="section-meta">Use input file paths for sandbox analysis. Leave the list empty to bias toward pure reasoning or web lookup.</p>
      </div>

      <form className="job-form" onSubmit={submit}>
        <label className="field">
          <span className="field__label">Prompt</span>
          <textarea
            className="field__textarea"
            value={query}
            placeholder="Ask the orchestrator to analyze files, summarize findings, or search external sources."
            onChange={(event) => setQuery(event.target.value)}
            disabled={disabled}
            rows={5}
          />
        </label>

        <div className="field-group">
          <label className="field field--grow">
            <span className="field__label">Input file path</span>
            <input
              className="field__input"
              type="text"
              value={fileDraft}
              placeholder="vlm_outputs/single_rooms_oneshot_20260421_113022.csv"
              onChange={(event) => setFileDraft(event.target.value)}
              onKeyDown={handleKeyDown}
              disabled={disabled}
            />
          </label>
          <button className="ghost-button" type="button" onClick={addInputFile} disabled={disabled}>
            Add file
          </button>
        </div>

        {inputFiles.length > 0 ? (
          <ul className="chip-list" aria-label="Selected input files">
            {inputFiles.map((filePath) => (
              <li className="chip" key={filePath}>
                <span>{filePath}</span>
                <button type="button" onClick={() => removeInputFile(filePath)} disabled={disabled}>
                  Remove
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="helper-text">No input files attached.</p>
        )}

        {error ? <p className="error-text">{error}</p> : null}

        <div className="form-actions">
          <button className="primary-button" type="submit" disabled={disabled}>
            {disabled ? 'Working…' : 'Create job'}
          </button>
        </div>
      </form>
    </section>
  )
}