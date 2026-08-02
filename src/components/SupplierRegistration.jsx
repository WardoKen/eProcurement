import React from 'react'

const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const ALLOWED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png']
const MAX_UPLOAD_SIZE = 10 * 1024 * 1024

const businessDocLabels = {
  'Sole Proprietorship': 'DTI Registration',
  'Corporation': 'SEC Registration',
  'Partnership': 'SEC Registration',
  'Cooperative': 'CDA Registration',
  'Others': null,
}

function getBusinessDocKey(businessType) {
  if (businessType === 'Sole Proprietorship') return 'dti_registration'
  if (businessType === 'Corporation' || businessType === 'Partnership') return 'sec_registration'
  if (businessType === 'Cooperative') return 'cda_registration'
  return null
}

function isSupportedFile(file) {
  if (!file) return false
  const name = (file.name || '').toLowerCase()
  const extension = name.slice(name.lastIndexOf('.'))
  const isValidExtension = ALLOWED_EXTENSIONS.includes(extension)
  const isValidMime = ['application/pdf', 'image/jpeg', 'image/png'].includes(file.type)
  return isValidExtension && (isValidMime || extension === '.pdf')
}

function validateEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}

function validatePhone(phone) {
  return /^(\+63|63|0)?[0-9\s\-]{7,15}$/.test(phone)
}

export default function SupplierRegistration({ apiBase = DEFAULT_API_BASE }) {
  const [step, setStep] = React.useState(1)
  const [form, setForm] = React.useState({
    companyName: '',
    businessType: 'Sole Proprietorship',
    businessAddress: '',
    contactPerson: '',
    email: '',
    contactNumber: '',
    productsServices: '',
    username: '',
    password: '',
    confirmPassword: '',
  })
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
  const [otherEligibilityFile, setOtherEligibilityFile] = React.useState(null)
  const [errors, setErrors] = React.useState([])
  const [message, setMessage] = React.useState('')
  const [submitting, setSubmitting] = React.useState(false)
  const [uploadProgress, setUploadProgress] = React.useState(0)
  const [submitted, setSubmitted] = React.useState(false)
  const [referenceNumber, setReferenceNumber] = React.useState('')

  function updateField(name, value) {
    setForm((current) => ({ ...current, [name]: value }))
  }

  function handleRequiredFileChange(key, file) {
    if (file && !isSupportedFile(file)) {
      setErrors([`${file.name} must be a PDF, JPG, JPEG, or PNG file.`])
      return
    }
    if (file && file.size > MAX_UPLOAD_SIZE) {
      setErrors([`${file.name} exceeds the 10MB upload limit.`])
      return
    }
    setRequiredFiles((current) => ({ ...current, [key]: file }))
    setErrors([])
  }

  function handleOtherEligibilityFileChange(file) {
    if (file && !isSupportedFile(file)) {
      setErrors([`${file.name} must be a PDF, JPG, JPEG, or PNG file.`])
      return
    }
    if (file && file.size > MAX_UPLOAD_SIZE) {
      setErrors([`${file.name} exceeds the 10MB upload limit.`])
      return
    }
    setOtherEligibilityFile(file)
    setErrors([])
  }

  function validateStep(nextStep) {
    const nextErrors = []

    if (nextStep >= 2) {
      if (!form.companyName.trim()) nextErrors.push('Company Name is required')
      if (!form.businessAddress.trim()) nextErrors.push('Business Address is required')
      if (!form.contactPerson.trim()) nextErrors.push('Contact Person is required')
      if (!form.email.trim() || !validateEmail(form.email.trim())) nextErrors.push('Email address must be valid')
      if (!form.contactNumber.trim() || !validatePhone(form.contactNumber.trim())) nextErrors.push('Phone number must be valid')
    }

    if (nextStep >= 3) {
      if (!form.productsServices.trim()) nextErrors.push('Products or services description is required')
    }

    if (nextStep >= 2) {
      if (!form.username.trim()) nextErrors.push('Account username is required')
      if (!form.password.trim()) nextErrors.push('Account password is required')
      if (form.password !== form.confirmPassword) nextErrors.push('Passwords do not match')
      if (form.password && form.password.length < 8) nextErrors.push('Password must be at least 8 characters long')
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
        if (!requiredFiles[doc.key]) nextErrors.push(`${doc.label} is required`)
      })
    }

    setErrors(nextErrors)
    return nextErrors.length === 0
  }

  function goNext() {
    if (validateStep(step + 1)) {
      setStep((current) => current + 1)
      setErrors([])
    }
  }

  function goBack() {
    setErrors([])
    setStep((current) => current - 1)
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
    formData.append('contactPerson', form.contactPerson.trim())
    formData.append('contactNumber', form.contactNumber.trim())
    formData.append('email', form.email.trim())
    formData.append('productsServices', form.productsServices.trim())
    formData.append('username', form.username.trim())
    formData.append('password', form.password)
    formData.append('confirmPassword', form.confirmPassword)

    Object.entries(requiredFiles).forEach(([key, file]) => {
      if (file) formData.append(key, file, file.name)
    })

    if (otherEligibilityFile) {
      formData.append('other_eligibility', otherEligibilityFile, otherEligibilityFile.name)
    }

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
        setStep(4)
        setForm({
          companyName: '',
          businessType: 'Sole Proprietorship',
          businessAddress: '',
          contactPerson: '',
          email: '',
          contactNumber: '',
          productsServices: '',
          username: '',
          password: '',
          confirmPassword: '',
        })
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
        setOtherEligibilityFile(null)
        setUploadProgress(0)
      } else {
        try {
          const response = JSON.parse(xhr.responseText || '{}')
          const serverErrors = response.errors || []
          if (serverErrors.length) setErrors(serverErrors)
          else setErrors([response.message || 'Registration failed. Please try again.'])
        } catch (error) {
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
  const documentCards = [
    { key: 'mayor_permit', label: "Mayor's Permit" },
    { key: 'philgeps_registration', label: 'PhilGEPS' },
    { key: 'bir_registration', label: 'BIR Registration' },
    { key: 'tax_clearance', label: 'Tax Clearance' },
    ...(businessDocLabel ? [{ key: getBusinessDocKey(form.businessType), label: businessDocLabel }] : []),
  ]

  const renderStepIndicator = () => (
    <div className="wizard-steps" role="list" aria-label="Registration progress">
      {[1, 2, 3, 4].map((item) => (
        <div key={item} className={`wizard-step ${step >= item ? 'active' : ''}`} role="listitem">
          <span className="wizard-step-number">{item}</span>
          <span className="wizard-step-label">{['Company & Account Setup', 'Products & Services', 'Document Uploads', 'Review & Submit'][item - 1]}</span>
        </div>
      ))}
    </div>
  )

  const renderStepContent = () => {
    if (submitted) {
      return (
        <section className="section-card success-card">
          <div className="success-icon">✓</div>
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
        <section className="section-card">
          <div className="section-header">
            <h2>Company Information</h2>
            <span className="section-badge">Step 1</span>
          </div>
          <div className="field-grid">
            <label className="form-field">
              <span>Company / Supplier Name *</span>
              <input value={form.companyName} onChange={(event) => updateField('companyName', event.target.value)} placeholder="e.g. Acme Supplies, Inc." required />
            </label>
            <label className="form-field">
              <span>Business Type *</span>
              <select value={form.businessType} onChange={(event) => updateField('businessType', event.target.value)}>
                <option>Sole Proprietorship</option>
                <option>Partnership</option>
                <option>Corporation</option>
                <option>Cooperative</option>
                <option>Others</option>
              </select>
            </label>
            <label className="form-field">
              <span>Business Address *</span>
              <input value={form.businessAddress} onChange={(event) => updateField('businessAddress', event.target.value)} placeholder="Street, City, Province" required />
            </label>
            <label className="form-field">
              <span>Contact Person *</span>
              <input value={form.contactPerson} onChange={(event) => updateField('contactPerson', event.target.value)} placeholder="Jane Doe" required />
            </label>
            <label className="form-field">
              <span>Email Address *</span>
              <input type="email" value={form.email} onChange={(event) => updateField('email', event.target.value)} placeholder="supplier@example.com" required />
            </label>
            <label className="form-field">
              <span>Phone Number *</span>
              <input value={form.contactNumber} onChange={(event) => updateField('contactNumber', event.target.value)} placeholder="09XX-XXX-XXXX" required />
            </label>
            <label className="form-field">
              <span>Username *</span>
              <input value={form.username} onChange={(event) => updateField('username', event.target.value)} placeholder="supplierdemo" required />
            </label>
            <label className="form-field">
              <span>Password *</span>
              <input type="password" value={form.password} onChange={(event) => updateField('password', event.target.value)} placeholder="At least 8 characters" required />
            </label>
            <label className="form-field">
              <span>Confirm Password *</span>
              <input type="password" value={form.confirmPassword} onChange={(event) => updateField('confirmPassword', event.target.value)} placeholder="Re-enter password" required />
            </label>
          </div>
        </section>
      )
    }

    if (step === 2) {
      return (
        <section className="section-card">
          <div className="section-header">
            <h2>Products / Services</h2>
            <span className="section-badge">Step 2</span>
          </div>
          <label className="form-field">
            <span>Products / Services *</span>
            <textarea rows="6" value={form.productsServices} onChange={(event) => updateField('productsServices', event.target.value)} placeholder="Supply and installation of air conditioning systems." required />
          </label>
        </section>
      )
    }

    if (step === 3) {
      return (
        <section className="section-card">
          <div className="section-header">
            <h2>Document Uploads</h2>
            <span className="section-badge">Step 3</span>
          </div>
          <p className="helper-text">Upload the required BAC eligibility documents in PDF, JPG, JPEG, or PNG format. Maximum size is 10 MB per file.</p>
          <div className="upload-grid">
            {documentCards.map((doc) => (
              <label key={doc.key} className="upload-card">
                <div className="upload-card-top">
                  <div>
                    <h3>{doc.label}</h3>
                    <p>PDF, JPG, JPEG, PNG</p>
                  </div>
                  <span className="upload-card-badge">Required</span>
                </div>
                <input type="file" accept=".pdf,image/jpeg,.jpg,.jpeg,.png" onChange={(event) => handleRequiredFileChange(doc.key, event.target.files[0])} />
                {requiredFiles[doc.key] ? (
                  <div className="file-chip">
                    <span>{requiredFiles[doc.key].name}</span>
                    <button type="button" onClick={() => handleRequiredFileChange(doc.key, null)}>Remove</button>
                  </div>
                ) : (
                  <div className="upload-placeholder">Choose file</div>
                )}
              </label>
            ))}
          </div>

          <label className="form-field upload-card optional-card">
            <div className="upload-card-top">
              <div>
                <h3>Other Eligibility Requirements</h3>
                <p>Optional supporting documents</p>
              </div>
              <span className="upload-card-badge optional">Optional</span>
            </div>
            <input type="file" accept=".pdf,image/jpeg,.jpg,.jpeg,.png" onChange={(event) => handleOtherEligibilityFileChange(event.target.files[0])} />
            {otherEligibilityFile ? (
              <div className="file-chip">
                <span>{otherEligibilityFile.name}</span>
                <button type="button" onClick={() => setOtherEligibilityFile(null)}>Remove</button>
              </div>
            ) : (
              <div className="upload-placeholder">Choose file</div>
            )}
          </label>
        </section>
      )
    }

    return (
      <section className="section-card">
        <div className="section-header">
          <h2>Review & Submit</h2>
          <span className="section-badge">Step 4</span>
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
            <p><strong>Contact Person:</strong> {form.contactPerson || '—'}</p>
            <p><strong>Email:</strong> {form.email || '—'}</p>
            <p><strong>Phone:</strong> {form.contactNumber || '—'}</p>
          </div>
          <div className="review-block">
            <h3>Products & Services</h3>
            <p><strong>Products / Services:</strong> {form.productsServices || '—'}</p>
          </div>
          <div className="review-block review-block-wide">
            <h3>Uploaded Documents</h3>
            <ul>
              {documentCards.filter((doc) => requiredFiles[doc.key]).map((doc) => (
                <li key={doc.key}>{doc.label}: {requiredFiles[doc.key].name}</li>
              ))}
              {otherEligibilityFile && <li>Other Eligibility Requirements: {otherEligibilityFile.name}</li>}
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
          <div className="error-list">
            <strong>Please fix the following issues:</strong>
            <ul>{errors.map((error) => <li key={error}>{error}</li>)}</ul>
          </div>
        )}

        {message && <div className="success-message">{message}</div>}

        {submitting && (
          <div className="progress-card">
            <div className="progress-track">
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
    </div>
  )
}
