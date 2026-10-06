const views = [...document.querySelectorAll('.view')];
const toast = document.querySelector('#toast');
const dialog = document.querySelector('#complaint-dialog');
let currentUser = null;
let toastTimer;
let adminComplaints = [];
let searchTimer;

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    credentials: 'same-origin',
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && !['/api/login', '/api/admin/login'].includes(path)) {
      currentUser = null;
      updateHeader();
      showView('home');
    }
    throw new Error(data.error || 'Something went wrong. Please try again.');
  }
  return data;
}

function updateHeader() {
  const authenticated = Boolean(currentUser);
  document.querySelector('#guest-actions').hidden = authenticated;
  document.querySelector('#logout-button').hidden = !authenticated;
  const label = document.querySelector('#signed-in-label');
  label.hidden = !authenticated;
  label.textContent = authenticated ? `${currentUser.name} · ${currentUser.role === 'admin' ? 'Warden' : 'Student'}` : '';
}

function showView(name) {
  const destination = currentUser?.role === 'admin' && name === 'dashboard' ? 'admin' : name;
  const target = document.querySelector(`#view-${destination}`);
  if (!target) return;
  views.forEach((view) => { view.hidden = view !== target; });
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showToast(message, isError = false) {
  window.clearTimeout(toastTimer);
  toast.textContent = message;
  toast.classList.toggle('error', isError);
  toast.classList.add('show');
  toastTimer = window.setTimeout(() => toast.classList.remove('show'), 3600);
}

function setMessage(element, message = '', isSuccess = false) {
  element.textContent = message;
  element.classList.toggle('success', isSuccess);
}

function escapeHtml(value = '') {
  return String(value).replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character]);
}

function statusClass(status) {
  return `status-${status.toLowerCase().replaceAll(' ', '-')}`;
}

function renderComplaint(complaint, allowFeedback = false) {
  const feedback = complaint.status === 'Resolved'
    ? (complaint.feedback_rating
      ? `<p class="feedback-submitted">Your rating: ${complaint.feedback_rating}/5 · ${escapeHtml(complaint.feedback_comment)}</p>`
      : allowFeedback ? `<form class="feedback-form" data-feedback-id="${complaint.id}">
          <label>Rating<select name="rating" required><option value="">Choose</option><option value="5">5 · Excellent</option><option value="4">4 · Good</option><option value="3">3 · Okay</option><option value="2">2 · Poor</option><option value="1">1 · Very poor</option></select></label>
          <label>Feedback<textarea name="comment" rows="2" maxlength="1000" placeholder="Share your experience" required></textarea></label>
          <button class="button button-dark" type="submit">Send feedback</button>
        </form>` : '')
    : '';
  return `<article class="complaint-entry">
    <div class="entry-head"><span class="entry-id">${escapeHtml(complaint.complaint_id || `#${complaint.id}`)} · ${escapeHtml(complaint.category)}</span><span class="status ${statusClass(complaint.status)}">${escapeHtml(complaint.status)}</span></div>
    <h3>${escapeHtml(complaint.title)}</h3>
    <p class="entry-meta">${escapeHtml(complaint.hostel_block)} · Room ${escapeHtml(complaint.room_number)} · <span class="entry-date">${escapeHtml(complaint.created_at)}</span></p>
    <p class="entry-description">${escapeHtml(complaint.description)}</p>
    <p class="resolution-note"><strong>Resolution remarks</strong>${escapeHtml(complaint.resolution_remarks || 'No remarks yet.')}</p>
    ${feedback}
    <button class="details-button" type="button" data-student-detail="${complaint.id}">View complaint details →</button>
  </article>`;
}

function renderComplaintList(target, complaints, allowFeedback = false) {
  target.innerHTML = complaints.length
    ? complaints.map((complaint) => renderComplaint(complaint, allowFeedback)).join('')
    : '<div class="empty-state">No complaints yet. Your requests will appear here.</div>';
}

async function loadStudentData() {
  const [{ profile, counts }, { complaints }] = await Promise.all([
    api('/api/dashboard'),
    api('/api/complaints'),
  ]);
  document.querySelector('#student-first-name').textContent = profile.name.trim().split(/\s+/)[0];
  document.querySelector('#student-room-line').textContent = `Student ${profile.student_id} · Room ${profile.room_number} · Block ${profile.hostel_block}`;
  document.querySelector('#count-total').textContent = counts.total;
  document.querySelector('#count-pending').textContent = counts.pending;
  document.querySelector('#count-in-progress').textContent = counts.in_progress;
  document.querySelector('#count-resolved').textContent = counts.resolved;
  renderComplaintList(document.querySelector('#recent-complaints'), complaints.slice(0, 3));
  document.querySelector('#complaint-room').value = profile.room_number;
  document.querySelector('#complaint-block').value = profile.hostel_block;
  renderComplaintList(document.querySelector('#all-complaints'), complaints);
  const resolved = complaints.filter((complaint) => complaint.status === 'Resolved');
  const feedbackList = document.querySelector('#feedback-list');
  if (resolved.length) {
    renderComplaintList(feedbackList, resolved, true);
  } else {
    feedbackList.innerHTML = '<div class="empty-state">Feedback becomes available after a complaint is marked resolved.</div>';
  }
  return complaints;
}

function adminQuery() {
  const params = new URLSearchParams();
  const search = document.querySelector('#admin-search').value.trim();
  const category = document.querySelector('#admin-category-filter').value;
  const status = document.querySelector('#admin-filter').value;
  if (search) params.set('q', search);
  if (category) params.set('category', category);
  if (status) params.set('status', status);
  return params.toString();
}

async function loadAdmin() {
  const query = adminQuery();
  const [list, dashboard] = await Promise.all([
    api(`/api/admin/complaints${query ? `?${query}` : ''}`),
    api('/api/admin/dashboard'),
  ]);
  adminComplaints = list.complaints;
  const counts = dashboard.counts;
  document.querySelector('#admin-total').textContent = `${counts.total} total ${counts.total === 1 ? 'request' : 'requests'}`;
  document.querySelector('#admin-count-total').textContent = counts.total;
  document.querySelector('#admin-count-pending').textContent = counts.pending;
  document.querySelector('#admin-count-progress').textContent = counts.in_progress;
  document.querySelector('#admin-count-resolved').textContent = counts.resolved;
  const tbody = document.querySelector('#admin-complaints');
  if (!adminComplaints.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No requests match these filters.</td></tr>';
    return;
  }
  tbody.innerHTML = adminComplaints.map((complaint) => `<tr>
    <td><strong>${escapeHtml(complaint.complaint_id)}</strong><small>${escapeHtml(complaint.category)}</small><button class="details-button" type="button" data-admin-detail="${complaint.id}">Open details</button></td>
    <td><strong>${escapeHtml(complaint.student_name)}</strong><small>${escapeHtml(complaint.student_id)} · ${escapeHtml(complaint.student_email)}<br>${escapeHtml(complaint.hostel_block)} · Room ${escapeHtml(complaint.room_number)}</small></td>
    <td><strong>${escapeHtml(complaint.title)}</strong><small>${escapeHtml(complaint.description)}</small></td>
    <td>${escapeHtml(complaint.created_at)}</td>
    <td><select class="status-select" aria-label="Status for ${escapeHtml(complaint.complaint_id)}" data-status-id="${complaint.id}">${['Pending', 'In Progress', 'Resolved', 'Rejected'].map((status) => `<option${complaint.status === status ? ' selected' : ''}>${status}</option>`).join('')}</select></td>
    <td><input class="remarks-input" type="text" maxlength="2000" aria-label="Resolution remarks" placeholder="Add remarks" value="${escapeHtml(complaint.resolution_remarks || '')}" data-remarks-id="${complaint.id}"></td>
    <td><button class="button button-dark" type="button" data-save-status="${complaint.id}">Save</button></td>
  </tr>`).join('');
}

function openDetails(complaint) {
  document.querySelector('#complaint-dialog-content').innerHTML = `<dl class="dialog-details">
    <dt>Complaint ID</dt><dd>${escapeHtml(complaint.complaint_id)}</dd>
    <dt>Student</dt><dd>${escapeHtml(complaint.student_name || currentUser.name)}${complaint.student_id ? ` · ${escapeHtml(complaint.student_id)}` : ''}</dd>
    <dt>Category</dt><dd>${escapeHtml(complaint.category)}</dd>
    <dt>Title</dt><dd>${escapeHtml(complaint.title)}</dd>
    <dt>Description</dt><dd>${escapeHtml(complaint.description)}</dd>
    <dt>Location</dt><dd>${escapeHtml(complaint.hostel_block)} · Room ${escapeHtml(complaint.room_number)}</dd>
    <dt>Date</dt><dd>${escapeHtml(complaint.created_at)}</dd>
    <dt>Status</dt><dd><span class="status ${statusClass(complaint.status)}">${escapeHtml(complaint.status)}</span></dd>
    <dt>Remarks</dt><dd>${escapeHtml(complaint.resolution_remarks || 'No resolution remarks yet.')}</dd>
  </dl>`;
  dialog.showModal();
}

document.addEventListener('click', async (event) => {
  const nav = event.target.closest('[data-nav]');
  if (nav) {
    event.preventDefault();
    const destination = nav.dataset.nav;
    try {
      if (['dashboard', 'complaints', 'feedback'].includes(destination) && currentUser?.role === 'student') await loadStudentData();
      if ((destination === 'dashboard' && currentUser?.role === 'admin') || destination === 'admin') await loadAdmin();
      showView(destination);
    } catch (error) {
      showToast(error.message, true);
    }
  }

  const save = event.target.closest('[data-save-status]');
  if (save) {
    const id = save.dataset.saveStatus;
    const status = document.querySelector(`[data-status-id="${id}"]`).value;
    const resolution_remarks = document.querySelector(`[data-remarks-id="${id}"]`).value;
    save.disabled = true;
    try {
      await api(`/api/admin/complaints/${id}/status`, { method: 'PUT', body: JSON.stringify({ status, resolution_remarks }) });
      await loadAdmin();
      showToast(`Complaint status saved as ${status}.`);
    } catch (error) {
      showToast(error.message, true);
    } finally {
      save.disabled = false;
    }
  }

  const studentDetail = event.target.closest('[data-student-detail]');
  if (studentDetail) {
    try {
      const { complaint } = await api(`/api/complaints/${studentDetail.dataset.studentDetail}`);
      openDetails(complaint);
    } catch (error) {
      showToast(error.message, true);
    }
  }

  const adminDetail = event.target.closest('[data-admin-detail]');
  if (adminDetail) {
    const complaint = adminComplaints.find((entry) => String(entry.id) === adminDetail.dataset.adminDetail);
    if (complaint) openDetails(complaint);
  }

  if (event.target.closest('[data-close-dialog]')) dialog.close();
});

document.querySelector('#login-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const message = document.querySelector('#login-message');
  setMessage(message);
  try {
    const result = await api('/api/login', { method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(form))) });
    currentUser = result.user;
    updateHeader();
    form.reset();
    await loadStudentData();
    showView('dashboard');
  } catch (error) {
    setMessage(message, error.message);
  }
});

document.querySelector('#admin-login-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const message = document.querySelector('#admin-login-message');
  setMessage(message);
  try {
    const result = await api('/api/admin/login', { method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(form))) });
    currentUser = result.user;
    updateHeader();
    form.reset();
    await loadAdmin();
    showView('admin');
  } catch (error) {
    setMessage(message, error.message);
  }
});

document.querySelector('#register-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = Object.fromEntries(new FormData(form));
  const message = document.querySelector('#register-message');
  setMessage(message);
  if (values.password !== values.password_confirmation) {
    setMessage(message, 'Passwords do not match.');
    return;
  }
  try {
    const result = await api('/api/register', { method: 'POST', body: JSON.stringify(values) });
    setMessage(message, `${result.message} Sign in with student ID ${values.student_id}.`, true);
    form.reset();
    window.setTimeout(() => showView('login'), 1200);
  } catch (error) {
    setMessage(message, error.message);
  }
});

document.querySelector('#complaint-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const message = document.querySelector('#complaint-message');
  setMessage(message);
  try {
    const result = await api('/api/complaints', { method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(form))) });
    setMessage(message, `${result.message} Your complaint ID is ${result.complaint_id}.`, true);
    form.reset();
    await loadStudentData();
  } catch (error) {
    setMessage(message, error.message);
  }
});

document.querySelector('#feedback-list').addEventListener('submit', async (event) => {
  const form = event.target.closest('[data-feedback-id]');
  if (!form) return;
  event.preventDefault();
  const complaintId = form.dataset.feedbackId;
  try {
    const result = await api(`/api/complaints/${complaintId}/feedback`, { method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(form))) });
    showToast(result.message);
    await loadStudentData();
  } catch (error) {
    showToast(error.message, true);
  }
});

document.querySelector('#logout-button').addEventListener('click', async () => {
  try {
    await api('/api/logout', { method: 'POST' });
    currentUser = null;
    updateHeader();
    showView('home');
    showToast('You have been logged out.');
  } catch (error) {
    showToast(error.message, true);
  }
});

document.querySelector('#admin-filter').addEventListener('change', () => loadAdmin().catch((error) => showToast(error.message, true)));
document.querySelector('#admin-category-filter').addEventListener('change', () => loadAdmin().catch((error) => showToast(error.message, true)));
document.querySelector('#admin-search').addEventListener('input', () => {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => loadAdmin().catch((error) => showToast(error.message, true)), 250);
});
document.querySelector('#footer-year').textContent = new Date().getFullYear();
document.querySelector('#dashboard-date').textContent = new Intl.DateTimeFormat('en', { weekday: 'long', month: 'long', day: 'numeric' }).format(new Date()).toUpperCase();

async function startApp() {
  try {
    const health = await fetch('/api/health');
    if (!health.ok) showToast('Website is running, but MySQL is unavailable. Configure MySQL to use saved accounts and complaints.', true);
    const { user } = await api('/api/session');
    currentUser = user;
    updateHeader();
    if (!currentUser) {
      showView('home');
      return;
    }
    if (currentUser.role === 'admin') {
      await loadAdmin();
      showView('admin');
    } else {
      await loadStudentData();
      showView('dashboard');
    }
  } catch {
    showView('home');
    showToast('The Flask API could not be reached.', true);
  }
}

startApp();
