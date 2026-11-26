import React from 'react'
import { apiFetch } from '../lib/apiClient'
import { Check, CheckCircle } from 'lucide-react'
import Modal from './ui/Modal'
import { FieldError, RequiredLegend, RequiredMark } from './ui/FormParts'
import PhoneField from './ui/PhoneField'
import GroupedDigitsInput from './ui/GroupedDigitsInput'
import DocumentUploadCard from './ui/DocumentUploadCard'
import { TIN_EXAMPLE, formatTin, isValidTin, parseTin } from '../lib/tin'
import { DEFAULT_PHONE_COUNTRY, findPhoneCountry, formatPhoneNumber, isValidPhoneNumber } from '../lib/phone'
import { UPLOAD_KINDS, acceptAttr, acceptedTypesLabel, validateFile } from '../lib/fileValidation'

const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const REQUIREMENT_KIND = UPLOAD_KINDS.SUPPLIER_REQUIREMENT
const REQUIREMENT_ACCEPT = acceptAttr(REQUIREMENT_KIND)

const businessDocLabels = {
  'Sole Proprietorship': 'DTI Registration',
  'Corporation': 'SEC Registration',
  'Partnership': 'SEC Registration',
  'Cooperative': 'CDA Registration',
  'Others': null,
}

// Extra supporting documents a supplier may attach; the backend enforces the
// same cap (MAX_OTHER_ELIGIBILITY_FILES in supplier_registration.py).
const MAX_OTHER_ELIGIBILITY_FILES = 10

const BUSINESS_DOC_HINTS = {
  'Sole Proprietorship': 'DTI Business Name Registration certificate',
  'Corporation': 'SEC Certificate of Incorporation',
  'Partnership': 'SEC Certificate of Registration',
  'Cooperative': 'CDA Certificate of Registration',
}

function getBusinessDocKey(businessType) {
  if (businessType === 'Sole Proprietorship') return 'dti_registration'
  if (businessType === 'Corporation' || businessType === 'Partnership') return 'sec_registration'
  if (businessType === 'Cooperative') return 'cda_registration'
  return null
}

function validateEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}

export default function SupplierRegistration({ apiBase = DEFAULT_API_BASE }) {
  const [step, setStep] = React.useState(1)
  const [categories, setCategories] = React.useState([])
  const [selectedCategoryIds, setSelectedCategoryIds] = React.useState([])
  const [categorySearchTerm, setCategorySearchTerm] = React.useState('')
  const [form, setForm] = React.useState({
    companyName: '',
    businessType: 'Sole Proprietorship',
    businessAddress: '',
    // Digits only; shown and submitted grouped as 123-456-789-000.
    tin: '',
    contactPerson: '',
    email: '',
    // National digits only; the dial code comes from phoneCountry.
    contactNumber: '',
    phoneCountry: DEFAULT_PHONE_COUNTRY,
    productsServices: '',
    username: '',
    password: '',
    confirmPassword: '',
  })
  const phoneCountry = findPhoneCountry(form.phoneCountry)
  const [requiredFiles, setRequiredFiles] = React.useState({
    mayor_permit: null,
    business_permit: null,
    philgeps_registration: null,
    bir_registration: null,
    tax_clearance: null,
    dti_registration: null,
    sec_registration: null,
    cda_registration: null,
  })
  const [otherEligibilityFiles, setOtherEligibilityFiles] = React.useState([])
  const [errors, setErrors] = React.useState([])
  const [fieldErrors, setFieldErrors] = React.useState({})
  const errorSummaryRef = React.useRef(null)
  const [message, setMessage] = React.useState('')
  const [submitting, setSubmitting] = React.useState(false)
  const [uploadProgress, setUploadProgress] = React.useState(0)
  const [submitted, setSubmitted] = React.useState(false)
  const [successModalOpen, setSuccessModalOpen] = React.useState(false)
  const [referenceNumber, setReferenceNumber] = React.useState('')
  const [showPassword, setShowPassword] = React.useState(false)

  React.useEffect(() => {
    let isMounted = true
    apiFetch(`${apiBase.replace(/\/$/, '')}/api/categories/`)
      .then((response) => {
        if (!response.ok) throw new Error('Failed to load categories')
        return response.json()
      })
      .then((data) => {
        if (isMounted) setCategories(Array.isArray(data) ? data : [])
      })
      .catch(() => {
        if (isMounted) setErrors(['Unable to load supplier categories. Please try again.'])
      })
    return () => { isMounted = false }
  }, [apiBase])

  function updateField(name, value) {
    setForm((current) => ({ ...current, [name]: value }))
    if (fieldErrors[name]) setFieldErrors((current) => ({ ...current, [name]: '' }))
  }

  function handleRequiredFileChange(key, file) {
    if (file) {
      const check = validateFile(file, REQUIREMENT_KIND)
      if (!check.ok) {
        // Shown on the document's own card and in the summary above.
        const message = `${file.name}: ${check.error}`
        setErrors([message])
        setFieldErrors((current) => ({ ...current, [key]: message }))
        return
      }
    }
    setRequiredFiles((current) => ({ ...current, [key]: file }))
    setErrors([])
    if (fieldErrors[key]) setFieldErrors((current) => ({ ...current, [key]: '' }))
  }

  // Adds the valid files from a pick or drop; invalid ones, duplicates of an
  // attached file, and any past the cap are left out and reported together.
  function handleOtherEligibilityFilesAdd(picked) {
    const sameFile = (a, b) => a.name === b.name && a.size === b.size && a.lastModified === b.lastModified
    const problems = []
    const accepted = []
    picked.forEach((file) => {
      const check = validateFile(file, REQUIREMENT_KIND)
      if (!check.ok) problems.push(`${file.name}: ${check.error}`)
      else if (![...otherEligibilityFiles, ...accepted].some((existing) => sameFile(existing, file))) accepted.push(file)
    })
    const room = MAX_OTHER_ELIGIBILITY_FILES - otherEligibilityFiles.length
    if (accepted.length > room) {
      problems.push(`Only ${MAX_OTHER_ELIGIBILITY_FILES} other eligibility documents can be attached; ${accepted.length - room} not added.`)
    }
    setOtherEligibilityFiles((current) => [...current, ...accepted.slice(0, Math.max(0, room))])
    const message = problems.join(' ')
    setErrors(message ? [message] : [])
    setFieldErrors((current) => ({ ...current, other_eligibility: message }))
  }

  function handleOtherEligibilityFileRemove(index) {
    setOtherEligibilityFiles((current) => current.filter((_, position) => position !== index))
    setFieldErrors((current) => ({ ...current, other_eligibility: '' }))
  }

  function validateStep(nextStep) {
    const nextErrors = []
    const nextFieldErrors = {}
    const add = (field, message) => {
      nextErrors.push(message)
      if (!nextFieldErrors[field]) nextFieldErrors[field] = message
    }

    if (nextStep >= 2) {
      if (!form.companyName.trim()) add('companyName', 'Company Name is required')
      if (!form.businessAddress.trim()) add('businessAddress', 'Business Address is required')
      if (!form.tin) add('tin', 'TIN Number is required')
      else if (!isValidTin(form.tin)) add('tin', `Enter a 9-digit TIN, with an optional 3- or 5-digit branch code, e.g. ${TIN_EXAMPLE}`)
      if (!form.contactPerson.trim()) add('contactPerson', 'Contact Person is required')
      if (!form.email.trim() || !validateEmail(form.email.trim())) add('email', 'Email address must be valid')
      if (!form.contactNumber) add('contactNumber', 'Phone Number is required')
      else if (!isValidPhoneNumber(form.contactNumber, phoneCountry)) add('contactNumber', `Enter a complete ${phoneCountry.name} number, e.g. +${phoneCountry.dial} ${phoneCountry.example}`)
    }

    if (nextStep >= 3) {
      if (!form.productsServices.trim()) add('productsServices', 'Products or services description is required')
      if (selectedCategoryIds.length === 0) add('categories', 'At least one supplier category must be selected')
    }

    if (nextStep >= 2) {
      if (!form.username.trim()) add('username', 'Account username is required')
      if (!form.password.trim()) add('password', 'Account password is required')
      if (form.password !== form.confirmPassword) add('confirmPassword', 'Passwords do not match')
      if (form.password && form.password.length < 8) add('password', 'Password must be at least 8 characters long')
    }

    if (nextStep === 4) {
      const requiredDocs = [
        { key: 'mayor_permit', label: "Mayor's Permit / Business Permit" },
        { key: 'business_permit', label: 'Business Permit' },
        { key: 'philgeps_registration', label: 'PhilGEPS Registration' },
        { key: 'bir_registration', label: 'BIR Registration' },
        { key: 'tax_clearance', label: 'Tax Clearance' },
      ]
      const businessDocKey = getBusinessDocKey(form.businessType)
      if (businessDocKey) {
        requiredDocs.push({ key: businessDocKey, label: businessDocLabels[form.businessType] })
      }
      requiredDocs.forEach((doc) => {
        if (!requiredFiles[doc.key]) add(doc.key, `${doc.label} is required`)
      })
    }

    setErrors(nextErrors)
    setFieldErrors(nextFieldErrors)
    if (nextErrors.length) window.setTimeout(() => errorSummaryRef.current?.focus(), 0)
    return nextErrors.length === 0
  }

  // Ids and ARIA wiring for one field. The visible label stays inside the
  // existing <label> wrapper; aria-labelledby keeps the inline error out of
  // the field's name while aria-describedby announces it.
  const fieldA11y = (key) => ({
    id: `reg-${key}`,
    'aria-labelledby': `reg-${key}-label`,
    'aria-invalid': fieldErrors[key] ? true : undefined,
    'aria-describedby': fieldErrors[key] ? `reg-${key}-error` : undefined,
  })
  const fieldLabel = (key, text, required = true) => (
    <span id={`reg-${key}-label`}>{text}{required && <RequiredMark />}</span>
  )
  const fieldError = (key) => <FieldError id={`reg-${key}-error`}>{fieldErrors[key]}</FieldError>
  // The step a field lives on, so the summary can say where to fix it.
  const FIELD_STEP = {
    companyName: 1, businessAddress: 1, tin: 1, contactPerson: 1, email: 1, contactNumber: 1, username: 1, password: 1, confirmPassword: 1,
    productsServices: 2, categories: 2,
  }
  const errorEntries = errors.map((message) => {
    const key = Object.keys(fieldErrors).find((field) => fieldErrors[field] === message)
    return { message, key, step: key ? (FIELD_STEP[key] || 3) : null }
  })

  function goNext() {
    if (validateStep(step + 1)) {
      setStep((current) => current + 1)
      setErrors([])
    }
  }

  function goBack() {
    setErrors([])
    setFieldErrors({})
    setStep((current) => current - 1)
  }

  function goToField(entry) {
    if (entry.step && entry.step < step && !submitted) {
      setStep(entry.step)
      window.setTimeout(() => document.getElementById(`reg-${entry.key}`)?.focus(), 0)
      return
    }
    document.getElementById(`reg-${entry.key}`)?.focus()
  }

  function submitForm(event) {
    event.preventDefault()
    setMessage('')
    setErrors([])
    if (!validateStep(4)) return

    setSubmitting(true)
    setUploadProgress(0)

    const formData = new FormData()
    formData.append('companyName', form.companyName.trim())
    formData.append('businessType', form.businessType)
    formData.append('businessAddress', form.businessAddress.trim())
    formData.append('tin', formatTin(form.tin))
    formData.append('contactPerson', form.contactPerson.trim())
    formData.append('contactNumber', formatPhoneNumber(form.contactNumber, phoneCountry))
    formData.append('email', form.email.trim())
    formData.append('productsServices', form.productsServices.trim())
    selectedCategoryIds.forEach((categoryId) => formData.append('category_ids', categoryId))
    formData.append('username', form.username.trim())
    formData.append('password', form.password)
    formData.append('confirmPassword', form.confirmPassword)

    Object.entries(requiredFiles).forEach(([key, file]) => {
      if (file) formData.append(key, file, file.name)
    })

    otherEligibilityFiles.forEach((file) => formData.append('other_eligibility', file, file.name))

    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${apiBase.replace(/\/$/, '')}/api/suppliers/register`)
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        setUploadProgress(Math.round((event.loaded / event.total) * 100))
      }
    }
    xhr.onload = () => {
      setSubmitting(false)
      if (xhr.status >= 200 && xhr.status < 300) {
        const response = JSON.parse(xhr.responseText || '{}')
        setMessage(response.message || 'Supplier registration submitted successfully. Please wait for review.')
        setReferenceNumber(`SUP-${new Date().getFullYear()}-${String(Math.floor(Math.random() * 9000) + 1000)}`)
        setSubmitted(true)
        setSuccessModalOpen(true)
        setStep(4)
        setForm({
          companyName: '',
          businessType: 'Sole Proprietorship',
          businessAddress: '',
          tin: '',
          contactPerson: '',
          email: '',
          contactNumber: '',
          phoneCountry: DEFAULT_PHONE_COUNTRY,
          productsServices: '',
          username: '',
          password: '',
          confirmPassword: '',
        })
        setSelectedCategoryIds([])
        setRequiredFiles({
          mayor_permit: null,
          business_permit: null,
          philgeps_registration: null,
          bir_registration: null,
          tax_clearance: null,
          dti_registration: null,
          sec_registration: null,
          cda_registration: null,
        })
        setOtherEligibilityFiles([])
        setUploadProgress(0)
      } else {
        try {
          const response = JSON.parse(xhr.responseText || '{}')
          const serverErrors = response.errors || []
          if (serverErrors.length) setErrors(serverErrors)
          else setErrors([response.message || 'Registration failed. Please try again.'])
        } catch {
          setErrors(['Registration failed. Please try again.'])
        }
      }
    }
    xhr.onerror = () => {
      setSubmitting(false)
      setErrors(['Network error during registration.'])
    }
    xhr.send(formData)
  }

  const businessDocLabel = businessDocLabels[form.businessType]
  const selectedCategories = categories.filter((category) => selectedCategoryIds.includes(category.id))
  const availableCategories = categories.filter((category) => (
    !selectedCategoryIds.includes(category.id)
    && category.name.toLowerCase().includes(categorySearchTerm.trim().toLowerCase())
  ))
  const documentCards = [
    { key: 'mayor_permit', label: "Mayor's Permit", hint: 'Current-year permit from your city or municipality' },
    { key: 'business_permit', label: 'Business Permit', hint: 'Valid business permit for the current year' },
    { key: 'philgeps_registration', label: 'PhilGEPS', hint: 'PhilGEPS Certificate of Registration' },
    { key: 'bir_registration', label: 'BIR Registration', hint: 'BIR Certificate of Registration (Form 2303)' },
    { key: 'tax_clearance', label: 'Tax Clearance', hint: 'Valid tax clearance issued by the BIR' },
    ...(businessDocLabel ? [{ key: getBusinessDocKey(form.businessType), label: businessDocLabel, hint: BUSINESS_DOC_HINTS[form.businessType] }] : []),
  ]

  const renderStepIndicator = () => (
    <div className="wizard-steps" role="list" aria-label="Registration progress">
      {[1, 2, 3, 4].map((item) => {
        const done = step > item || submitted
        const current = step === item && !submitted
        return (
        <div key={item} className={`wizard-step ${done ? 'is-done' : current ? 'is-current' : 'is-upcoming'}`} role="listitem" aria-current={current ? 'step' : undefined}>
          <span className="wizard-step-number" aria-hidden="true">{done ? <Check size={14} strokeWidth={3} /> : String(item).padStart(2, '0')}</span>
          <span className="wizard-step-label">{['Company & Account Setup', 'Products & Services', 'Document Uploads', 'Review & Submit'][item - 1]}</span>
          <span className="sr-only">{done ? ' (completed)' : current ? ` (current step, ${item} of 4)` : ''}</span>
        </div>
        )
      })}
    </div>
  )

  const renderStepContent = () => {
    if (submitted) {
      return (
        <section className="section-card success-card">
          <div className="success-icon" aria-hidden="true"><CheckCircle size={28} /></div>
          <h2>Registration Submitted Successfully</h2>
          <p>Your supplier registration has been submitted for BAC review.</p>
          <p>You will be notified once your application has been approved or if additional requirements are needed.</p>
          <div className="reference-box">
            <span>Reference Number</span>
            <strong>{referenceNumber}</strong>
          </div>
        </section>
      )
    }

    if (step === 1) {
      return (
        <>
        <section className="section-card">
          <div className="section-header">
            <h2>Company Information</h2>
          </div>
          <RequiredLegend />
          <div className="field-grid">
            <label className="form-field">
              {fieldLabel('companyName', 'Company / Supplier Name')}
              <input {...fieldA11y('companyName')} value={form.companyName} onChange={(event) => updateField('companyName', event.target.value)} placeholder="e.g. Acme Supplies, Inc." required />
              {fieldError('companyName')}
            </label>
            <label className="form-field">
              {fieldLabel('businessType', 'Business Type')}
              <select {...fieldA11y('businessType')} value={form.businessType} onChange={(event) => updateField('businessType', event.target.value)}>
                <option>Sole Proprietorship</option>
                <option>Partnership</option>
                <option>Corporation</option>
                <option>Cooperative</option>
                <option>Others</option>
              </select>
            </label>
            <label className="form-field">
              {fieldLabel('businessAddress', 'Business Address')}
              <input {...fieldA11y('businessAddress')} value={form.businessAddress} onChange={(event) => updateField('businessAddress', event.target.value)} placeholder="Street, City, Province" required />
              {fieldError('businessAddress')}
            </label>
            <label className="form-field">
              {fieldLabel('tin', 'TIN Number')}
              <GroupedDigitsInput
                {...fieldA11y('tin')}
                inputMode="numeric"
                autoComplete="off"
                placeholder={`e.g. ${TIN_EXAMPLE}`}
                required
                digits={form.tin}
                format={formatTin}
                parse={(raw) => ({ digits: parseTin(raw) })}
                onChange={({ digits }) => updateField('tin', digits)}
              />
              {fieldError('tin')}
            </label>
            <label className="form-field">
              {fieldLabel('contactPerson', 'Contact Person')}
              <input {...fieldA11y('contactPerson')} value={form.contactPerson} onChange={(event) => updateField('contactPerson', event.target.value)} placeholder="Jane Doe" required />
              {fieldError('contactPerson')}
            </label>
            <label className="form-field">
              {fieldLabel('email', 'Email Address')}
              <input {...fieldA11y('email')} type="email" value={form.email} onChange={(event) => updateField('email', event.target.value)} placeholder="supplier@example.com" required />
              {fieldError('email')}
            </label>
            {/* A div, not a label: the field holds two controls (country code and number). */}
            <div className="form-field">
              {fieldLabel('contactNumber', 'Phone Number')}
              <PhoneField
                id="reg-contactNumber"
                countryCode={form.phoneCountry}
                digits={form.contactNumber}
                onChange={({ countryCode, digits }) => {
                  setForm((current) => ({ ...current, phoneCountry: countryCode }))
                  updateField('contactNumber', digits)
                }}
                inputProps={{ ...fieldA11y('contactNumber'), required: true }}
              />
              {fieldError('contactNumber')}
            </div>
          </div>
        </section>
        <section className="section-card account-setup-card">
          <div className="section-header">
            <h2>Account Setup</h2>
          </div>
          <p className="helper-text">Create the login credentials you will use to access the supplier portal.</p>
          <div className="field-grid account-setup-fields">
            <label className="form-field">
              {fieldLabel('username', 'Username')}
              <input {...fieldA11y('username')} value={form.username} onChange={(event) => updateField('username', event.target.value)} placeholder="supplierdemo" required />
              {fieldError('username')}
            </label>
            <label className="form-field password-field">
              {fieldLabel('password', 'Password')}
              <div className="password-input-wrapper">
                <input {...fieldA11y('password')} type={showPassword ? 'text' : 'password'} autoComplete="new-password" value={form.password} onChange={(event) => updateField('password', event.target.value)} placeholder="At least 8 characters" required />
                <button type="button" className="password-toggle" onClick={() => setShowPassword((current) => !current)} aria-pressed={showPassword} aria-label={showPassword ? 'Hide passwords' : 'Show passwords'}>
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
              {fieldError('password')}
            </label>
            <label className="form-field password-field">
              {fieldLabel('confirmPassword', 'Confirm Password')}
              <div className="password-input-wrapper">
                <input {...fieldA11y('confirmPassword')} type={showPassword ? 'text' : 'password'} autoComplete="new-password" value={form.confirmPassword} onChange={(event) => updateField('confirmPassword', event.target.value)} placeholder="Re-enter password" required />
                <button type="button" className="password-toggle" onClick={() => setShowPassword((current) => !current)} aria-pressed={showPassword} aria-label={showPassword ? 'Hide passwords' : 'Show passwords'}>
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
              {fieldError('confirmPassword')}
            </label>
          </div>
        </section>
        </>
      )
    }

    if (step === 2) {
      return (
        <section className="section-card">
          <div className="section-header">
            <h2>Products / Services</h2>
          </div>
          <label className="form-field">
            {fieldLabel('productsServices', 'Products / Services')}
            <textarea {...fieldA11y('productsServices')} rows="6" value={form.productsServices} onChange={(event) => updateField('productsServices', event.target.value)} placeholder="Supply and installation of air conditioning systems." required />
            {fieldError('productsServices')}
          </label>
          <div className="form-field">
            <span id="reg-categories-label">Supplier Categories<RequiredMark /></span>
            <p className="helper-text" id="reg-categories-hint">Select all categories that match the products or services your company can provide.</p>
            {fieldError('categories')}
            <div className="category-search">
              <input
                type="search"
                value={categorySearchTerm}
                onChange={(event) => setCategorySearchTerm(event.target.value)}
                placeholder="Search supplier categories"
                aria-label="Search supplier categories"
              />
            </div>
            <div
              className="category-groups"
              role="group"
              id="reg-categories"
              tabIndex={-1}
              aria-labelledby="reg-categories-label"
              aria-describedby={fieldErrors.categories ? 'reg-categories-hint reg-categories-error' : 'reg-categories-hint'}
            >
              <div className="category-group">
                <div className="category-group-header">
                  <strong>Selected Categories</strong>
                  <span>{selectedCategories.length}</span>
                </div>
                <div className="multi-select category-list selected-category-list">
                  {selectedCategories.length > 0 ? selectedCategories.map((category) => (
                    <label key={category.id} className="category-option">
                      <input
                        type="checkbox"
                        checked
                        onChange={() => setSelectedCategoryIds((current) => current.filter((id) => id !== category.id))}
                      />
                      <span>{category.name}</span>
                    </label>
                  )) : <span className="helper-text">No categories selected yet.</span>}
                </div>
              </div>
              <div className="category-group">
                <div className="category-group-header">
                  <strong>Available Categories</strong>
                  <span>{availableCategories.length}</span>
                </div>
                <div className="multi-select category-list">
                  {availableCategories.length > 0 ? availableCategories.map((category) => (
                    <label key={category.id} className="category-option">
                      <input
                        type="checkbox"
                        checked={false}
                        onChange={() => {
                          setSelectedCategoryIds((current) => [...current, category.id])
                          if (fieldErrors.categories) setFieldErrors((current) => ({ ...current, categories: '' }))
                        }}
                      />
                      <span>{category.name}</span>
                    </label>
                  )) : <span className="helper-text">No matching categories found.</span>}
                </div>
              </div>
            </div>
          </div>
        </section>
      )
    }

    if (step === 3) {
      const attachedCount = documentCards.filter((doc) => requiredFiles[doc.key]).length
      const allAttached = attachedCount === documentCards.length
      const acceptLabel = `${acceptedTypesLabel(REQUIREMENT_KIND)} · up to 10 MB`
      return (
        <section className="section-card">
          <div className="section-header">
            <h2>Document Uploads</h2>
          </div>
          <div className={`doc-checklist-summary${allAttached ? ' is-complete' : ''}`}>
            <div className="doc-checklist-summary-text">
              <span className="doc-checklist-kicker">BAC eligibility documents</span>
              <strong>{attachedCount} of {documentCards.length} required documents attached</strong>
              <p>Upload a clear scan or photo of each current document. One file per document; {acceptLabel}.</p>
            </div>
            <div
              className="doc-checklist-meter"
              role="progressbar"
              aria-label="Required documents attached"
              aria-valuemin={0}
              aria-valuemax={documentCards.length}
              aria-valuenow={attachedCount}
            >
              <span style={{ width: `${(attachedCount / documentCards.length) * 100}%` }} />
            </div>
          </div>

          <div className="upload-grid">
            {documentCards.map((doc) => (
              <DocumentUploadCard
                key={doc.key}
                id={`reg-${doc.key}`}
                title={doc.label}
                hint={doc.hint}
                file={requiredFiles[doc.key]}
                error={fieldErrors[doc.key]}
                accept={REQUIREMENT_ACCEPT}
                acceptLabel={acceptLabel}
                onSelect={(file) => handleRequiredFileChange(doc.key, file)}
                onRemove={() => handleRequiredFileChange(doc.key, null)}
              />
            ))}
            <DocumentUploadCard
              id="reg-other_eligibility"
              title="Other Eligibility Requirements"
              hint="Any additional supporting documents the BAC asked for. Add as many as you need."
              required={false}
              multiple
              files={otherEligibilityFiles}
              maxFiles={MAX_OTHER_ELIGIBILITY_FILES}
              error={fieldErrors.other_eligibility}
              accept={REQUIREMENT_ACCEPT}
              acceptLabel={acceptLabel}
              onSelect={handleOtherEligibilityFilesAdd}
              onRemove={handleOtherEligibilityFileRemove}
            />
          </div>
        </section>
      )
    }

    return (
      <section className="section-card">
        <div className="section-header">
          <h2>Review & Submit</h2>
        </div>
        <p className="helper-text">Please confirm your account setup and details before submitting for BAC review.</p>
        <div className="review-grid">
          <div className="review-block">
            <h3>Account Setup</h3>
            <p><strong>Username:</strong> {form.username || '—'}</p>
            <p><strong>Password:</strong> ••••••••</p>
          </div>
          <div className="review-block">
            <h3>Company Details</h3>
            <p><strong>Company Name:</strong> {form.companyName || '—'}</p>
            <p><strong>Business Type:</strong> {form.businessType}</p>
            <p><strong>Business Address:</strong> {form.businessAddress || '—'}</p>
            <p><strong>TIN:</strong> {formatTin(form.tin) || '—'}</p>
            <p><strong>Contact Person:</strong> {form.contactPerson || '—'}</p>
            <p><strong>Email:</strong> {form.email || '—'}</p>
            <p><strong>Phone:</strong> {formatPhoneNumber(form.contactNumber, phoneCountry) || '—'}</p>
          </div>
          <div className="review-block">
            <h3>Products & Services</h3>
            <p><strong>Products / Services:</strong> {form.productsServices || '—'}</p>
            <p><strong>Categories:</strong> {selectedCategories.map((category) => category.name).join(', ') || '—'}</p>
          </div>
          <div className="review-block review-block-wide">
            <h3>Uploaded Documents</h3>
            <ul>
              {documentCards.filter((doc) => requiredFiles[doc.key]).map((doc) => (
                <li key={doc.key}>{doc.label}: {requiredFiles[doc.key].name}</li>
              ))}
              {otherEligibilityFiles.map((file, index) => <li key={`${file.name}-${index}`}>Other Eligibility Requirements: {file.name}</li>)}
            </ul>
          </div>
        </div>
      </section>
    )
  }

  return (
    <div className="page-content registration-page">
      <div className="registration-hero">
        <div>
          <p className="eyebrow">Supplier onboarding</p>
          <h1>Register your company for BAC review</h1>
          <p>Complete a simple supplier registration experience with clear guidance, document uploads, and account setup.</p>
        </div>
      </div>

      {renderStepIndicator()}

      <form onSubmit={submitForm} className="registration-form">
        {renderStepContent()}

        {errors.length > 0 && (
          <div className="error-list" role="alert" tabIndex={-1} ref={errorSummaryRef}>
            <strong>Please fix the following {errors.length === 1 ? 'issue' : `${errors.length} issues`}:</strong>
            <ul>
              {errorEntries.map((entry) => (
                <li key={entry.message}>
                  {entry.key ? (
                    <button type="button" className="link-like" onClick={() => goToField(entry)}>
                      {entry.message}{entry.step && entry.step < step ? ` (Step ${entry.step})` : ''}
                    </button>
                  ) : entry.message}
                </li>
              ))}
            </ul>
          </div>
        )}

        {message && <div className="success-message" role="status">{message}</div>}

        {submitting && (
          <div className="progress-card" role="status" aria-live="polite">
            <div className="progress-track" role="progressbar" aria-label="Upload progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={uploadProgress}>
              <div className="progress-fill" style={{ width: `${uploadProgress}%` }} />
            </div>
            <span>{uploadProgress}% uploaded</span>
          </div>
        )}

        <div className="form-actions wizard-actions">
          {step > 1 && !submitted && <button type="button" className="btn-secondary" onClick={goBack}>Back</button>}
          {step < 4 && !submitted && <button type="button" className="btn-primary" onClick={goNext}>Continue</button>}
          {step === 4 && !submitted && <button type="submit" className="btn-primary" disabled={submitting}>{submitting ? 'Submitting...' : 'Submit Registration'}</button>}
        </div>
      </form>

      {successModalOpen && (
        <Modal
          labelledBy="supplier-registration-success-title"
          className="modal-content registration-success-modal"
          onClose={() => setSuccessModalOpen(false)}
        >
            <div className="modal-header">
              <h2 id="supplier-registration-success-title">Registration Submitted Successfully</h2>
              <button
                type="button"
                className="modal-close"
                onClick={() => setSuccessModalOpen(false)}
                aria-label="Close registration confirmation"
              >
                ×
              </button>
            </div>
            <div className="modal-body registration-success-modal-body">
              <div className="success-icon" aria-hidden="true"><CheckCircle size={28} /></div>
              <p>Supplier registration submitted successfully. It is now pending review.</p>
              <div className="reference-box">
                <span>Reference Number</span>
                <strong>{referenceNumber}</strong>
              </div>
            </div>
            <div className="modal-actions">
              <button type="button" className="btn btn-primary" onClick={() => setSuccessModalOpen(false)}>
                Continue
              </button>
            </div>
        </Modal>
      )}
    </div>
  )
}
