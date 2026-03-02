'use strict';

Modals.ReferenceDocuments = (() => {
        let documents = [];
        let filteredDocuments = [];
        let currentFilters = {
            search: '',
            category: '',
            contentType: '',
            availableForTask: null
        };

        function formatFileSize(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
        }

        function formatDateAustralian(dateString) {
            if (!dateString) return 'No Date';
            try {
                const date = new Date(dateString);
                if (isNaN(date.getTime())) return 'Invalid Date';
                
                const day = String(date.getDate()).padStart(2, '0');
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const year = date.getFullYear();
                const hours = String(date.getHours()).padStart(2, '0');
                const minutes = String(date.getMinutes()).padStart(2, '0');
                
                return `${day}/${month}/${year} ${hours}:${minutes}`;
            } catch (error) {
                return 'Invalid Date';
            }
        }

        function getFileIcon(contentType) {
            if (!contentType) return { class: 'fas fa-file', color: '#666' };
            
            if (contentType === 'application/pdf') {
                return { class: 'fas fa-file-pdf', color: '#dc3545' };
            }
            
            if (contentType.includes('word') || contentType.includes('msword') || contentType.includes('document')) {
                return { class: 'fas fa-file-word', color: '#2b579a' };
            }
            
            if (contentType.includes('excel') || contentType.includes('spreadsheet')) {
                return { class: 'fas fa-file-excel', color: '#1d6f42' };
            }
            
            if (contentType.includes('powerpoint') || contentType.includes('presentation')) {
                return { class: 'fas fa-file-powerpoint', color: '#d04423' };
            }
            
            if (contentType.startsWith('image/')) {
                return { class: 'fas fa-file-image', color: '#17a2b8' };
            }
            
            if (contentType === 'application/json') {
                return { class: 'fas fa-file-code', color: '#f39c12' };
            }
            
            if (contentType.includes('text') || contentType === 'text/csv') {
                return { class: 'fas fa-file-alt', color: '#17a2b8' };
            }
            
            return { class: 'fas fa-file', color: '#666' };
        }

        async function loadDocuments() {
            if (!DOM.referenceDocumentsList) return;
            
            DOM.referenceDocumentsList.innerHTML = '<div style="text-align: center; padding: 2rem; color: #666;">Loading documents...</div>';
            
            try {
                const params = new URLSearchParams();
                if (currentFilters.search) params.append('search', currentFilters.search);
                if (currentFilters.category) params.append('category', currentFilters.category);
                if (currentFilters.contentType) {
                    if (currentFilters.contentType === 'image') {
                        params.append('content_type', 'image/');
                    } else if (currentFilters.contentType === 'text') {
                        params.append('content_type', 'text/');
                    } else {
                        params.append('content_type', currentFilters.contentType);
                    }
                }
                if (currentFilters.availableForTask !== null) {
                    params.append('available_for_task', currentFilters.availableForTask.toString());
                }
                
                const response = await fetch(`/reference-documents?${params.toString()}`);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                documents = await response.json();
                filteredDocuments = documents;
                renderDocuments();
            } catch (error) {
                console.error("Failed to load reference documents:", error);
                DOM.referenceDocumentsList.innerHTML = '<div style="text-align: center; padding: 2rem; color: #dc3545;">Failed to load documents: ' + error.message + '</div>';
            }
        }

        function renderDocuments() {
            if (!DOM.referenceDocumentsList) return;
            
            if (filteredDocuments.length === 0) {
                DOM.referenceDocumentsList.innerHTML = '<div style="text-align: center; padding: 2rem; color: #666;">No documents found</div>';
                return;
            }
            
            DOM.referenceDocumentsList.innerHTML = '';
            
            filteredDocuments.forEach(doc => {
                const docCard = document.createElement('div');
                docCard.className = 'reference-document-item';
                docCard.style.cssText = 'padding: 1em; margin-bottom: 0.75em; border: 1px solid #e9ecef; border-radius: 6px; background: #ffffff; cursor: pointer; transition: all 0.2s ease;';
                
                const icon = getFileIcon(doc.content_type);
                
                docCard.innerHTML = `
                    <div style="display: flex; align-items: flex-start; gap: 1em;">
                        <div style="font-size: 2em; color: ${icon.color}; flex-shrink: 0;">
                            <i class="${icon.class}"></i>
                        </div>
                        <div style="flex: 1; min-width: 0;">
                            <div style="font-weight: 600; color: #233366; margin-bottom: 0.25em; font-size: 1em;">
                                ${doc.title || doc.filename}
                            </div>
                            <div style="font-size: 0.85em; color: #666; margin-bottom: 0.25em;">
                                ${doc.filename} • ${formatFileSize(doc.size)} • ${formatDateAustralian(doc.created_at)}
                            </div>
                            ${doc.description ? `<div style="font-size: 0.85em; color: #888; margin-bottom: 0.25em;">${doc.description.substring(0, 100)}${doc.description.length > 100 ? '...' : ''}</div>` : ''}
                            ${doc.author ? `<div style="font-size: 0.8em; color: #999;">Author: ${doc.author}</div>` : ''}
                            ${doc.available_for_task ? '<div style="font-size: 0.8em; color: #28a745; margin-top: 0.25em;"><i class="fas fa-check-circle"></i> Available for Task</div>' : ''}
                        </div>
                        <div style="display: flex; flex-direction: row; gap: 0.5em; flex-shrink: 0; align-items: center;">
                            ${doc.content_type.startsWith('image/') ? 
                                `<button class="reference-document-view-btn" data-doc-id="${doc.id}" style="padding: 0.4em 0.8em; font-size: 0.85em; background: #4a90e2; color: white; border: none; border-radius: 4px; cursor: pointer;">
                                    <i class="fas fa-eye"></i> View
                                </button>` :
                                `<button class="reference-document-download-btn" data-doc-id="${doc.id}" style="padding: 0.4em 0.8em; font-size: 0.85em; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer;">
                                    <i class="fas fa-download"></i> Download
                                </button>`
                            }
                            <button class="reference-document-edit-btn" data-doc-id="${doc.id}" style="padding: 0.4em 0.8em; font-size: 0.85em; background: #6c757d; color: white; border: none; border-radius: 4px; cursor: pointer;">
                                <i class="fas fa-edit"></i> Edit
                            </button>
                            <button class="reference-document-delete-btn" data-doc-id="${doc.id}" style="padding: 0.4em 0.8em; font-size: 0.85em; background: #dc3545; color: white; border: none; border-radius: 4px; cursor: pointer;">
                                <i class="fas fa-trash"></i> Delete
                            </button>
                        </div>
                    </div>
                `;
                
                // Add event listeners
                const viewBtn = docCard.querySelector('.reference-document-view-btn');
                if (viewBtn) {
                    viewBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        viewDocument(parseInt(viewBtn.dataset.docId));
                    });
                }
                
                const downloadBtn = docCard.querySelector('.reference-document-download-btn');
                if (downloadBtn) {
                    downloadBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        downloadDocument(parseInt(downloadBtn.dataset.docId));
                    });
                }
                
                const editBtn = docCard.querySelector('.reference-document-edit-btn');
                if (editBtn) {
                    editBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        editDocument(parseInt(editBtn.dataset.docId));
                    });
                }
                
                const deleteBtn = docCard.querySelector('.reference-document-delete-btn');
                if (deleteBtn) {
                    deleteBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        deleteDocument(parseInt(deleteBtn.dataset.docId));
                    });
                }
                
                DOM.referenceDocumentsList.appendChild(docCard);
            });
        }

        function viewDocument(documentId) {
            const doc = documents.find(d => d.id === documentId);
            if (!doc) return;
            
            if (doc.content_type.startsWith('image/')) {
                // Show image in modal
                if (DOM.singleImageModal && DOM.singleImageModalImg) {
                    if (DOM.singleImageModalAudio) DOM.singleImageModalAudio.style.display = 'none';
                    if (DOM.singleImageModalVideo) DOM.singleImageModalVideo.style.display = 'none';
                    if (DOM.singleImageModalPdf) DOM.singleImageModalPdf.style.display = 'none';
                    
                    DOM.singleImageModalImg.src = `/reference-documents/${documentId}/download`;
                    DOM.singleImageModalImg.alt = doc.title || doc.filename;
                    DOM.singleImageModalImg.style.display = 'block';
                    
                    if (DOM.singleImageDetails) {
                        const details = [];
                        if (doc.title) details.push(`<strong>Title:</strong> ${doc.title}`);
                        if (doc.description) details.push(`<strong>Description:</strong> ${doc.description}`);
                        if (doc.author) details.push(`<strong>Author:</strong> ${doc.author}`);
                        if (doc.filename) details.push(`<strong>Filename:</strong> ${doc.filename}`);
                        if (doc.created_at) details.push(`<strong>Date:</strong> ${formatDateAustralian(doc.created_at)}`);
                        DOM.singleImageDetails.innerHTML = details.length > 0 ? details.join('<br>') : '';
                    }
                    
                    Modals._openModal(DOM.singleImageModal);
                }
            } else {
                // Download document
                downloadDocument(documentId);
            }
        }

        function downloadDocument(documentId) {
            window.open(`/reference-documents/${documentId}/download`, '_blank');
        }

        async function editDocument(documentId) {
            const doc = documents.find(d => d.id === documentId);
            if (!doc) return;
            
            // Populate edit form
            document.getElementById('reference-documents-edit-id').value = doc.id;
            document.getElementById('reference-documents-edit-title').value = doc.title || '';
            document.getElementById('reference-documents-edit-description').value = doc.description || '';
            document.getElementById('reference-documents-edit-author').value = doc.author || '';
            document.getElementById('reference-documents-edit-tags').value = doc.tags || '';
            document.getElementById('reference-documents-edit-categories').value = doc.categories || '';
            document.getElementById('reference-documents-edit-notes').value = doc.notes || '';
            document.getElementById('reference-documents-edit-task').checked = doc.available_for_task || false;
            
            Modals._openModal(DOM.referenceDocumentsEditModal);
        }

        async function deleteDocument(documentId) {
            if (!confirm('Are you sure you want to delete this document?')) {
                return;
            }
            
            try {
                const response = await fetch(`/reference-documents/${documentId}`, {
                    method: 'DELETE'
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                await loadDocuments();
                // Reset notification flag when document is deleted
                Modals.ReferenceDocumentsNotification.reset();
            } catch (error) {
                console.error("Failed to delete document:", error);
                alert('Failed to delete document: ' + error.message);
            }
        }

        function applyFilters() {
            currentFilters.search = DOM.referenceDocumentsSearch.value.trim();
            currentFilters.category = DOM.referenceDocumentsCategoryFilter.value;
            currentFilters.contentType = DOM.referenceDocumentsContentTypeFilter.value;
            currentFilters.availableForTask = DOM.referenceDocumentsTaskFilter.checked ? true : null;
            
            loadDocuments();
        }

        function init() {
            if (DOM.closeReferenceDocumentsModalBtn) {
                DOM.closeReferenceDocumentsModalBtn.addEventListener('click', close);
            }
            
            if (DOM.referenceDocumentsModal) {
                DOM.referenceDocumentsModal.addEventListener('click', (e) => {
                    if (e.target === DOM.referenceDocumentsModal) close();
                });
            }
            
            if (DOM.referenceDocumentsSearch) {
                let searchTimeout;
                DOM.referenceDocumentsSearch.addEventListener('input', () => {
                    clearTimeout(searchTimeout);
                    searchTimeout = setTimeout(() => {
                        applyFilters();
                    }, 300);
                });
            }
            
            if (DOM.referenceDocumentsCategoryFilter) {
                DOM.referenceDocumentsCategoryFilter.addEventListener('change', applyFilters);
            }
            
            if (DOM.referenceDocumentsContentTypeFilter) {
                DOM.referenceDocumentsContentTypeFilter.addEventListener('change', applyFilters);
            }
            
            if (DOM.referenceDocumentsTaskFilter) {
                DOM.referenceDocumentsTaskFilter.addEventListener('change', applyFilters);
            }
            
            if (DOM.referenceDocumentsUploadBtn) {
                DOM.referenceDocumentsUploadBtn.addEventListener('click', () => {
                    Modals._openModal(DOM.referenceDocumentsUploadModal);
                });
            }
            
            if (DOM.closeReferenceDocumentsUploadModalBtn) {
                DOM.closeReferenceDocumentsUploadModalBtn.addEventListener('click', () => {
                    Modals._closeModal(DOM.referenceDocumentsUploadModal);
                });
            }
            
            if (DOM.referenceDocumentsUploadCancelBtn) {
                DOM.referenceDocumentsUploadCancelBtn.addEventListener('click', () => {
                    Modals._closeModal(DOM.referenceDocumentsUploadModal);
                    DOM.referenceDocumentsUploadForm.reset();
                });
            }
            
            if (DOM.referenceDocumentsUploadForm) {
                DOM.referenceDocumentsUploadForm.addEventListener('submit', async (e) => {
                    e.preventDefault();
                    
                    const formData = new FormData();
                    const fileInput = document.getElementById('reference-documents-upload-file');
                    if (!fileInput.files[0]) {
                        alert('Please select a file');
                        return;
                    }
                    
                    formData.append('file', fileInput.files[0]);
                    formData.append('title', document.getElementById('reference-documents-upload-title').value);
                    formData.append('description', document.getElementById('reference-documents-upload-description').value);
                    formData.append('author', document.getElementById('reference-documents-upload-author').value);
                    formData.append('tags', document.getElementById('reference-documents-upload-tags').value);
                    formData.append('categories', document.getElementById('reference-documents-upload-categories').value);
                    formData.append('notes', document.getElementById('reference-documents-upload-notes').value);
                    formData.append('available_for_task', document.getElementById('reference-documents-upload-task').checked);
                    
                    try {
                        const response = await fetch('/reference-documents', {
                            method: 'POST',
                            body: formData
                        });
                        
                        if (!response.ok) {
                            const error = await response.json();
                            throw new Error(error.detail || `HTTP error! status: ${response.status}`);
                        }
                        
                        Modals._closeModal(DOM.referenceDocumentsUploadModal);
                        DOM.referenceDocumentsUploadForm.reset();
                        await loadDocuments();
                        // Reset notification flag when document is added
                        Modals.ReferenceDocumentsNotification.reset();
                    } catch (error) {
                        console.error("Failed to upload document:", error);
                        alert('Failed to upload document: ' + error.message);
                    }
                });
            }
            
            if (DOM.closeReferenceDocumentsEditModalBtn) {
                DOM.closeReferenceDocumentsEditModalBtn.addEventListener('click', () => {
                    Modals._closeModal(DOM.referenceDocumentsEditModal);
                });
            }
            
            if (DOM.referenceDocumentsEditCancelBtn) {
                DOM.referenceDocumentsEditCancelBtn.addEventListener('click', () => {
                    Modals._closeModal(DOM.referenceDocumentsEditModal);
                });
            }
            
            if (DOM.referenceDocumentsEditForm) {
                DOM.referenceDocumentsEditForm.addEventListener('submit', async (e) => {
                    e.preventDefault();
                    
                    const documentId = parseInt(document.getElementById('reference-documents-edit-id').value);
                    const updateData = {
                        title: document.getElementById('reference-documents-edit-title').value || null,
                        description: document.getElementById('reference-documents-edit-description').value || null,
                        author: document.getElementById('reference-documents-edit-author').value || null,
                        tags: document.getElementById('reference-documents-edit-tags').value || null,
                        categories: document.getElementById('reference-documents-edit-categories').value || null,
                        notes: document.getElementById('reference-documents-edit-notes').value || null,
                        available_for_task: document.getElementById('reference-documents-edit-task').checked
                    };
                    
                    try {
                        const response = await fetch(`/reference-documents/${documentId}`, {
                            method: 'PUT',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify(updateData)
                        });
                        
                        if (!response.ok) {
                            const error = await response.json();
                            throw new Error(error.detail || `HTTP error! status: ${response.status}`);
                        }
                        
                        Modals._closeModal(DOM.referenceDocumentsEditModal);
                        await loadDocuments();
                        // Reset notification flag when document is edited
                        Modals.ReferenceDocumentsNotification.reset();
                    } catch (error) {
                        console.error("Failed to update document:", error);
                        alert('Failed to update document: ' + error.message);
                    }
                });
            }
        }

        function open() {
            Modals._openModal(DOM.referenceDocumentsModal);
            loadDocuments();
        }

        function close() {
            Modals._closeModal(DOM.referenceDocumentsModal);
        }

        return { init, open, close };
})();


Modals.ReferenceDocumentsNotification = (() => {
        let proceedCallback = null;
        let hasShownBefore = false;
        let numberOfCalls = 0;
        const STORAGE_KEY = 'reference_documents_notification_shown';
        const STORAGE_KEY_DOCS_HASH = 'reference_documents_hash';

        async function fetchReferenceDocuments() {
            try {
                // Fetch all reference documents (not just those with available_for_task=true)
                const response = await fetch('/reference-documents');
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return await response.json();
            } catch (error) {
                console.error('Error fetching reference documents:', error);
                return [];
            }
        }

        function getDocumentsHash(documents) {
            // Create a hash of all document IDs and their available_for_task status
            const allDocs = documents
                .map(doc => `${doc.id}:${doc.available_for_task}`)
                .sort()
                .join(',');
            return allDocs;
        }

        function renderDocumentsList(documents) {
            if (!DOM.referenceDocumentsNotificationList) return;

            if (documents.length === 0) {
                DOM.referenceDocumentsNotificationList.innerHTML = 
                    '<div style="text-align: center; padding: 1rem; color: #666;">No reference documents found.</div>';
                return;
            }

            // Separate selected and non-selected documents
            const selectedDocs = documents.filter(doc => doc.available_for_task === true);
            const nonSelectedDocs = documents.filter(doc => doc.available_for_task !== true);

            DOM.referenceDocumentsNotificationList.innerHTML = '';

            // Show selected documents section
            if (selectedDocs.length > 0) {
                const sectionHeader = document.createElement('div');
                sectionHeader.style.cssText = 'font-weight: 600; color: #28a745; margin-bottom: 0.75rem; margin-top: 0.5rem; font-size: 0.95em;';
                sectionHeader.textContent = `Selected for Chat (${selectedDocs.length}):`;
                DOM.referenceDocumentsNotificationList.appendChild(sectionHeader);

                selectedDocs.forEach(doc => {
                    const docItem = document.createElement('div');
                    docItem.style.cssText = 'padding: 0.75rem; margin-bottom: 0.5rem; border: 1px solid #28a745; border-radius: 6px; background: #f0f9f4;';
                    
                    const title = document.createElement('div');
                    title.style.cssText = 'font-weight: 600; color: #233366; margin-bottom: 0.25rem;';
                    title.textContent = doc.title || doc.filename;
                    
                    const details = document.createElement('div');
                    details.style.cssText = 'font-size: 0.85em; color: #666;';
                    details.textContent = `${doc.filename}${doc.author ? ` • ${doc.author}` : ''}`;
                    
                    docItem.appendChild(title);
                    docItem.appendChild(details);
                    DOM.referenceDocumentsNotificationList.appendChild(docItem);
                });
            }

            // Show non-selected documents section
            if (nonSelectedDocs.length > 0) {
                const sectionHeader = document.createElement('div');
                sectionHeader.style.cssText = 'font-weight: 600; color: #6c757d; margin-bottom: 0.75rem; margin-top: 1rem; font-size: 0.95em;';
                sectionHeader.textContent = `Not Selected (${nonSelectedDocs.length}):`;
                DOM.referenceDocumentsNotificationList.appendChild(sectionHeader);

                nonSelectedDocs.forEach(doc => {
                    const docItem = document.createElement('div');
                    docItem.style.cssText = 'padding: 0.75rem; margin-bottom: 0.5rem; border: 1px solid #e9ecef; border-radius: 6px; background: #f8f9fa; opacity: 0.7;';
                    
                    const title = document.createElement('div');
                    title.style.cssText = 'font-weight: 600; color: #6c757d; margin-bottom: 0.25rem;';
                    title.textContent = doc.title || doc.filename;
                    
                    const details = document.createElement('div');
                    details.style.cssText = 'font-size: 0.85em; color: #999;';
                    details.textContent = `${doc.filename}${doc.author ? ` • ${doc.author}` : ''}`;
                    
                    docItem.appendChild(title);
                    docItem.appendChild(details);
                    DOM.referenceDocumentsNotificationList.appendChild(docItem);
                });
            }

            // Show message if no documents are selected
            if (selectedDocs.length === 0) {
                const noSelectionMsg = document.createElement('div');
                noSelectionMsg.style.cssText = 'text-align: center; padding: 1rem; color: #dc3545; font-style: italic; margin-top: 0.5rem;';
                noSelectionMsg.textContent = 'No documents are currently set to be included in chat.';
                DOM.referenceDocumentsNotificationList.appendChild(noSelectionMsg);
            }
        }

        async function checkAndShow(callback) {
         
            proceedCallback = callback;
            
            // Check if we should show the notification
            const documents = await fetchReferenceDocuments();
            
            const currentHash = getDocumentsHash(documents);
            const storedHash = localStorage.getItem(STORAGE_KEY_DOCS_HASH);
            //const hasShownBefore = localStorage.getItem(STORAGE_KEY) === 'true';
            
            // Show if:
            // 1. User hasn't seen it before, OR
            // 2. Documents have changed (hash differs)
            const shouldShow = !hasShownBefore || (storedHash !== currentHash || numberOfCalls > 15);
            
            if (shouldShow) {
                renderDocumentsList(documents);
                open();
                // Update hash after showing
                localStorage.setItem(STORAGE_KEY_DOCS_HASH, currentHash);
                hasShownBefore = true;
                numberOfCalls = 0;
            } else {
                numberOfCalls++;
                // No need to show, proceed directly
                if (callback) callback();
            }
        }

        function open() {
            if (DOM.referenceDocumentsNotificationModal) {
                DOM.referenceDocumentsNotificationModal.style.display = 'flex';
            }
        }

        function close() {
            if (DOM.referenceDocumentsNotificationModal) {
                DOM.referenceDocumentsNotificationModal.style.display = 'none';
            }
            proceedCallback = null;
        }

        function proceed() {
            // Mark as shown
            localStorage.setItem(STORAGE_KEY, 'true');
            
            if (proceedCallback) {
                proceedCallback();
            }
            close();
        }

        function cancel() {
            close();
            // Don't mark as shown if user cancels
        }

        function reset() {
            // Reset the flag when documents change
            localStorage.removeItem(STORAGE_KEY);
        }

        function init() {
            if (DOM.closeReferenceDocumentsNotificationModalBtn) {
                DOM.closeReferenceDocumentsNotificationModalBtn.addEventListener('click', cancel);
            }
            
            if (DOM.referenceDocumentsNotificationCancelBtn) {
                DOM.referenceDocumentsNotificationCancelBtn.addEventListener('click', cancel);
            }
            
            if (DOM.referenceDocumentsNotificationProceedBtn) {
                DOM.referenceDocumentsNotificationProceedBtn.addEventListener('click', proceed);
            }
            
            if (DOM.referenceDocumentsNotificationModal) {
                DOM.referenceDocumentsNotificationModal.addEventListener('click', (e) => {
                    if (e.target === DOM.referenceDocumentsNotificationModal) {
                        cancel();
                    }
                });
            }
        }

        return { init, checkAndShow, reset };
})();


Modals.ConversationManager = (() => {
        let currentConversationId = null;
        let currentConversationTitle = null;

        // Store conversation state
        const CONVERSATION_STORAGE_KEY = 'current_conversation_id';
        const CONVERSATION_TITLE_STORAGE_KEY = 'current_conversation_title';

        async function fetchConversations() {
            try {
                const response = await fetch('/chat/conversations');
                if (!response.ok) {
                    const errorText = await response.text();
                    console.error(`HTTP error! status: ${response.status}, body: ${errorText}`);
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const data = await response.json();
                console.log('Fetched conversations:', data);
                return data;
            } catch (error) {
                console.error('Error fetching conversations:', error);
                return [];
            }
        }

        async function createConversation(title, voice) {
            try {
                const response = await fetch('/chat/conversations', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title, voice })
                });
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
                }
                return await response.json();
            } catch (error) {
                console.error('Error creating conversation:', error);
                throw error;
            }
        }

        async function deleteConversation(conversationId) {
            try {
                const response = await fetch(`/chat/conversations/${conversationId}`, {
                    method: 'DELETE'
                });
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
                }
                return await response.json();
            } catch (error) {
                console.error('Error deleting conversation:', error);
                throw error;
            }
        }

        async function updateConversationTitle(conversationId, newTitle) {
            try {
                const response = await fetch(`/chat/conversations/${conversationId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: newTitle })
                });
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
                }
                return await response.json();
            } catch (error) {
                console.error('Error updating conversation title:', error);
                throw error;
            }
        }

        async function getConversation(conversationId) {
            try {
                const response = await fetch(`/chat/conversations/${conversationId}`);
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
                }
                return await response.json();
            } catch (error) {
                console.error('Error getting conversation:', error);
                throw error;
            }
        }

        function renderConversationList(conversations) {
            if (!DOM.conversationListContainer) {
                console.error('conversationListContainer not found in DOM');
                return;
            }

            console.log('Rendering conversations:', conversations);
            DOM.conversationListContainer.innerHTML = '';

            if (!conversations || conversations.length === 0) {
                const noConvsMsg = document.createElement('div');
                noConvsMsg.style.cssText = 'text-align: center; padding: 2rem; color: #666;';
                noConvsMsg.textContent = 'No conversations found. Create a new one to get started!';
                DOM.conversationListContainer.appendChild(noConvsMsg);
                return;
            }

            conversations.forEach(conv => {
                const convItem = document.createElement('div');
                convItem.style.cssText = 'padding: 1rem; margin-bottom: 0.75rem; border: 1px solid #ddd; border-radius: 8px; background: #fff; cursor: pointer; transition: background 0.2s;';
                convItem.style.cursor = 'pointer';
                convItem.onmouseover = () => convItem.style.background = '#f5f5f5';
                convItem.onmouseout = () => convItem.style.background = '#fff';

                const titleRow = document.createElement('div');
                titleRow.style.cssText = 'display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;';

                const titleDiv = document.createElement('div');
                titleDiv.style.cssText = 'font-weight: 600; color: #233366; font-size: 1.05em;';
                titleDiv.textContent = conv.title;
                titleRow.appendChild(titleDiv);

                const actionsDiv = document.createElement('div');
                actionsDiv.style.cssText = 'display: flex; gap: 0.5rem;';

                // Edit title button
                const editBtn = document.createElement('button');
                editBtn.innerHTML = '<i class="fa-solid fa-pencil"></i>';
                editBtn.style.cssText = 'padding: 0.25rem 0.5rem; border: 1px solid #ddd; border-radius: 4px; background: #fff; cursor: pointer;';
                editBtn.title = 'Edit title';
                editBtn.onclick = (e) => {
                    e.stopPropagation();
                    editConversationTitle(conv.id, conv.title);
                };
                actionsDiv.appendChild(editBtn);

                // Delete button
                const deleteBtn = document.createElement('button');
                deleteBtn.innerHTML = '<i class="fa-solid fa-trash"></i>';
                deleteBtn.style.cssText = 'padding: 0.25rem 0.5rem; border: 1px solid #dc3545; border-radius: 4px; background: #fff; color: #dc3545; cursor: pointer;';
                deleteBtn.title = 'Delete conversation';
                deleteBtn.onclick = (e) => {
                    e.stopPropagation();
                    deleteConversationWithConfirm(conv.id);
                };
                actionsDiv.appendChild(deleteBtn);

                titleRow.appendChild(actionsDiv);
                convItem.appendChild(titleRow);

                const detailsDiv = document.createElement('div');
                detailsDiv.style.cssText = 'font-size: 0.85em; color: #666; margin-top: 0.25rem;';
                const lastMsgDate = conv.last_message_at ? new Date(conv.last_message_at).toLocaleString() : 'No messages yet';
                detailsDiv.textContent = `${conv.turn_count} messages • ${lastMsgDate}`;
                convItem.appendChild(detailsDiv);

                // Resume conversation on click
                convItem.onclick = () => {
                    resumeConversation(conv.id);
                };

                DOM.conversationListContainer.appendChild(convItem);
            });
        }

        async function editConversationTitle(conversationId, currentTitle) {
            const newTitle = prompt('Enter new conversation title:', currentTitle);
            if (newTitle && newTitle.trim() && newTitle !== currentTitle) {
                try {
                    await updateConversationTitle(conversationId, newTitle.trim());
                    showConversationList(); // Refresh list
                    if (currentConversationId === conversationId) {
                        currentConversationTitle = newTitle.trim();
                        updateConversationIndicator();
                    }
                } catch (error) {
                    alert(`Error updating title: ${error.message}`);
                }
            }
        }

        async function deleteConversationWithConfirm(conversationId) {
            if (!confirm('Are you sure you want to delete this conversation? This action cannot be undone.')) {
                return;
            }

            try {
                await deleteConversation(conversationId);
                if (currentConversationId === conversationId) {
                    // If deleting current conversation, clear it
                    currentConversationId = null;
                    currentConversationTitle = null;
                    updateConversationIndicator();
                    Chat.clearChat();
                }
                showConversationList(); // Refresh list
            } catch (error) {
                alert(`Error deleting conversation: ${error.message}`);
            }
        }

        async function resumeConversation(conversationId) {
            try {
                // Get conversation details with turns
                const conversation = await getConversation(conversationId);
                
                // Set current conversation
                currentConversationId = conversationId;
                currentConversationTitle = conversation.title;
                localStorage.setItem(CONVERSATION_STORAGE_KEY, conversationId.toString());
                localStorage.setItem(CONVERSATION_TITLE_STORAGE_KEY, conversation.title);
                
                // Clear chat display
                Chat.clearChat();
                
                // Load and display up to 30 messages
                const turns = conversation.turns || [];
                const displayTurns = turns.slice(-30); // Get last 30 turns
                
                displayTurns.forEach(turn => {
                    Chat.addMessage('user', turn.user_input, false);
                    Chat.addMessage('assistant', turn.response_text, true);
                });
                
                // Set voice if different
                if (conversation.voice && VoiceSelector) {
                    VoiceSelector.setVoice(conversation.voice);
                }
                
                // Update conversation indicator
                updateConversationIndicator();
                
                // Close modal
                close();
                
                // Scroll to bottom
                UI.scrollToBottom();
            } catch (error) {
                console.error('Error resuming conversation:', error);
                alert(`Error resuming conversation: ${error.message}`);
            }
        }

        async function createNewConversation() {
            if (!DOM.newConversationTitleInput || !DOM.newConversationVoiceSelect) {
                alert('New conversation form elements not found');
                return;
            }

            const title = DOM.newConversationTitleInput.value.trim();
            const voice = DOM.newConversationVoiceSelect.value;

            if (!title) {
                alert('Please enter a conversation title');
                return;
            }

            try {
                const conversation = await createConversation(title, voice);
                
                // Set as current conversation
                currentConversationId = conversation.id;
                currentConversationTitle = conversation.title;
                localStorage.setItem(CONVERSATION_STORAGE_KEY, conversation.id.toString());
                localStorage.setItem(CONVERSATION_TITLE_STORAGE_KEY, conversation.title);
                
                // Clear chat and update indicator
                Chat.clearChat();
                updateConversationIndicator();
                
                // Close modals
                close();
                if (DOM.newConversationModal) {
                    Modals._closeModal(DOM.newConversationModal);
                }
                
                // Clear form
                DOM.newConversationTitleInput.value = '';
                
                // Refresh conversation list
                showConversationList();
            } catch (error) {
                alert(`Error creating conversation: ${error.message}`);
            }
        }

        function updateConversationIndicator() {
            if (DOM.conversationIndicator) {
                if (currentConversationTitle) {
                    DOM.conversationIndicator.textContent = `Conversation: ${currentConversationTitle}`;
                    DOM.conversationIndicator.style.display = 'block';
                } else {
                    DOM.conversationIndicator.style.display = 'none';
                }
            }
        }

        function getCurrentConversationId() {
            return currentConversationId;
        }

        function clearCurrentConversation() {
            currentConversationId = null;
            currentConversationTitle = null;
            updateConversationIndicator();
        }

        function loadStoredConversation() {
            const storedId = localStorage.getItem(CONVERSATION_STORAGE_KEY);
            const storedTitle = localStorage.getItem(CONVERSATION_TITLE_STORAGE_KEY);
            if (storedId) {
                currentConversationId = parseInt(storedId);
                currentConversationTitle = storedTitle;
                updateConversationIndicator();
            }
        }

        async function showConversationList() {
            if (!DOM.conversationListModal) {
                console.error('Conversation list modal not found');
                return;
            }

            Modals._openModal(DOM.conversationListModal);
            
            // Show loading
            if (DOM.conversationListContainer) {
                DOM.conversationListContainer.innerHTML = '<div style="text-align: center; padding: 2rem;">Loading conversations...</div>';
            }

            try {
                const conversations = await fetchConversations();
                renderConversationList(conversations);
            } catch (error) {
                console.error('Error loading conversations:', error);
                if (DOM.conversationListContainer) {
                    DOM.conversationListContainer.innerHTML = `<div style="text-align: center; padding: 2rem; color: #dc3545;">Error loading conversations: ${error.message}</div>`;
                }
            }
        }

        function showNewConversationModal(e) {
            if (e) {
                e.preventDefault();
                e.stopPropagation();
            }
            if (!DOM.newConversationModal) {
                console.error('New conversation modal not found');
                return;
            }
            Modals._openModal(DOM.newConversationModal);
            
            // Set default voice if available
            if (DOM.newConversationVoiceSelect && VoiceSelector) {
                DOM.newConversationVoiceSelect.value = VoiceSelector.getSelectedVoice();
            }
        }

        function close(e) {
            if (e) {
                e.preventDefault();
                e.stopPropagation();
            }
            if (DOM.conversationListModal) {
                Modals._closeModal(DOM.conversationListModal);
            }
        }

        function init() {
            // Do not load stored conversation on page reload
            // loadStoredConversation();

            // Set up event listeners
            if (DOM.closeConversationListModalBtn) {
                DOM.closeConversationListModalBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    close(e);
                });
            }

            if (DOM.newConversationBtn) {
                DOM.newConversationBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    showNewConversationModal(e);
                });
            }

            if (DOM.createConversationBtn) {
                DOM.createConversationBtn.addEventListener('click', createNewConversation);
            }

            if (DOM.closeNewConversationModalBtn) {
                DOM.closeNewConversationModalBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    if (DOM.newConversationModal) {
                        Modals._closeModal(DOM.newConversationModal);
                    }
                });
            }

            // Cancel button in new conversation modal footer
            const cancelNewConversationBtn = document.getElementById('cancel-new-conversation-btn');
            if (cancelNewConversationBtn) {
                cancelNewConversationBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    if (DOM.newConversationModal) {
                        Modals._closeModal(DOM.newConversationModal);
                    }
                });
            }

            if (DOM.conversationListModal) {
                DOM.conversationListModal.addEventListener('click', (e) => {
                    if (e.target === DOM.conversationListModal) {
                        close();
                    }
                });
            }

            if (DOM.newConversationModal) {
                DOM.newConversationModal.addEventListener('click', (e) => {
                    if (e.target === DOM.newConversationModal) {
                        Modals._closeModal(DOM.newConversationModal);
                    }
                });
            }
        }

        return { 
            init, 
            showConversationList, 
            resumeConversation, 
            createNewConversation,
            getCurrentConversationId,
            updateConversationIndicator,
            clearCurrentConversation
        };
})();


Modals.SubjectConfiguration = (() => {
        let currentSubjectName = null;
        let currentGender = null;
        let configurationLoaded = false;

        async function loadConfiguration() {
            try {
                const response = await fetch('/api/subject-configuration');
                if (response.ok) {
                    const config = await response.json();
                    currentSubjectName = config.subject_name;
                    currentGender = config.gender || 'Male';
                    configurationLoaded = true;
                    return config;
                } else if (response.status === 404) {
                    // Configuration doesn't exist yet
                    configurationLoaded = false;
                    return null;
                } else {
                    throw new Error(`Failed to load configuration: ${response.statusText}`);
                }
            } catch (error) {
                console.error('Error loading subject configuration:', error);
                configurationLoaded = false;
                return null;
            }
        }

        function switchTab(tabName) {
            // Hide all tab contents
            const tabContents = document.querySelectorAll('.subject-config-tab-content');
            tabContents.forEach(content => {
                content.style.display = 'none';
            });

            // Remove active class from all tabs
            const tabs = document.querySelectorAll('.subject-config-tab');
            tabs.forEach(tab => {
                tab.classList.remove('active');
            });

            // Show selected tab content
            const selectedContent = document.getElementById(`${tabName}-tab-content`);
            if (selectedContent) {
                selectedContent.style.display = 'block';
            }

            // Add active class to selected tab
            const selectedTab = document.querySelector(`.subject-config-tab[data-tab="${tabName}"]`);
            if (selectedTab) {
                selectedTab.classList.add('active');
            }
        }

        function _renderWritingStyleMarkdown(text) {
            if (!DOM.writingStyleDisplay) return;
            if (!text || !text.trim()) {
                DOM.writingStyleDisplay.innerHTML = '<span style="color: #999;">No writing style summary yet. Click "Generate Writing Style" to analyze messages.</span>';
                return;
            }
            try {
                if (typeof marked !== 'undefined') {
                    DOM.writingStyleDisplay.innerHTML = marked.parse(text);
                } else {
                    DOM.writingStyleDisplay.textContent = text;
                }
            } catch (e) {
                console.error('Error rendering writing style markdown:', e);
                DOM.writingStyleDisplay.textContent = text;
            }
        }

        function _renderPsychologicalProfileMarkdown(text) {
            if (!DOM.psychologicalProfileDisplay) return;
            if (!text || !text.trim()) {
                DOM.psychologicalProfileDisplay.innerHTML = '<span style="color: #999;">No psychological profile yet. Click "Generate Psychological Profile" to analyze messages.</span>';
                return;
            }
            try {
                if (typeof marked !== 'undefined') {
                    DOM.psychologicalProfileDisplay.innerHTML = marked.parse(text);
                } else {
                    DOM.psychologicalProfileDisplay.textContent = text;
                }
            } catch (e) {
                console.error('Error rendering psychological profile markdown:', e);
                DOM.psychologicalProfileDisplay.textContent = text;
            }
        }

        async function requestWritingStyle() {
            if (!DOM.requestWritingStyleBtn || !DOM.writingStyleLoading || !DOM.writingStyleDisplay) return;
            DOM.requestWritingStyleBtn.disabled = true;
            DOM.writingStyleLoading.style.display = 'block';
            DOM.writingStyleDisplay.innerHTML = '';
            try {
                const response = await fetch('/writing-style/summarize', { method: 'POST' });
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.detail || 'Failed to generate writing style');
                }
                _renderWritingStyleMarkdown(data.summary || '');
            } catch (error) {
                console.error('Error requesting writing style:', error);
                DOM.writingStyleDisplay.innerHTML = `<span style="color: #c00;">Error: ${error.message}</span>`;
            } finally {
                DOM.requestWritingStyleBtn.disabled = false;
                DOM.writingStyleLoading.style.display = 'none';
            }
        }

        async function requestPsychologicalProfile() {
            if (!DOM.requestPsychologicalProfileBtn || !DOM.psychologicalProfileLoading || !DOM.psychologicalProfileDisplay) return;
            DOM.requestPsychologicalProfileBtn.disabled = true;
            DOM.psychologicalProfileLoading.style.display = 'block';
            DOM.psychologicalProfileDisplay.innerHTML = '';
            try {
                const response = await fetch('/psychological-profile/summarize', { method: 'POST' });
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.detail || 'Failed to generate psychological profile');
                }
                _renderPsychologicalProfileMarkdown(data.profile || '');
            } catch (error) {
                console.error('Error requesting psychological profile:', error);
                DOM.psychologicalProfileDisplay.innerHTML = `<span style="color: #c00;">Error: ${error.message}</span>`;
            } finally {
                DOM.requestPsychologicalProfileBtn.disabled = false;
                DOM.psychologicalProfileLoading.style.display = 'none';
            }
        }

        async function saveConfiguration(subjectName, systemInstructions, gender, familyName, otherNames, emailAddresses, phoneNumbers, whatsappHandle, instagramHandle) {
            try {
                const response = await fetch('/api/subject-configuration', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        subject_name: subjectName,
                        system_instructions: systemInstructions,
                        gender: gender || 'Male',
                        family_name: familyName || null,
                        other_names: otherNames || null,
                        email_addresses: emailAddresses || null,
                        phone_numbers: phoneNumbers || null,
                        whatsapp_handle: whatsappHandle || null,
                        instagram_handle: instagramHandle || null
                    })
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Failed to save configuration');
                }

                const config = await response.json();
                currentSubjectName = config.subject_name;
                currentGender = config.gender || 'Male';
                configurationLoaded = true;
                return config;
            } catch (error) {
                console.error('Error saving subject configuration:', error);
                throw error;
            }
        }

        function getSubjectName() {
            return currentSubjectName;
        }


        async function checkAndShow() {
            // if (configurationLoaded && currentSubjectName) {
            //     updatePageReferences(currentSubjectName, currentGender);
            //     return;
            // }

            const config = await loadConfiguration();
            if (!config) {
                // No configuration exists, show modal
                showModal();
            } else {
                // Configuration exists, update references
                //updatePageReferences(config.subject_name, config.gender || 'Male');
            }
        }

        let isInitialSetup = false;

        async function showModal(loadExisting = false) {
            if (!DOM.subjectConfigurationModal) {
                console.error('Subject configuration modal not found');
                return;
            }

            // Track if this is initial setup (non-dismissible) or editing (dismissible)
            isInitialSetup = !loadExisting;

            // Load existing configuration if requested (for editing)
            if (loadExisting) {
                try {
                    const config = await loadConfiguration();
                    if (config) {
                        if (DOM.subjectNameInput) {
                            DOM.subjectNameInput.value = config.subject_name || '';
                        }
                        if (DOM.subjectGenderSelect) {
                            DOM.subjectGenderSelect.value = config.gender || 'Male';
                        }
                        if (DOM.familyNameInput) {
                            DOM.familyNameInput.value = config.family_name || '';
                        }
                        if (DOM.otherNamesInput) {
                            DOM.otherNamesInput.value = config.other_names || '';
                        }
                        if (DOM.emailAddressesInput) {
                            DOM.emailAddressesInput.value = config.email_addresses || '';
                        }
                        if (DOM.phoneNumbersInput) {
                            DOM.phoneNumbersInput.value = config.phone_numbers || '';
                        }
                        if (DOM.whatsappHandleInput) {
                            DOM.whatsappHandleInput.value = config.whatsapp_handle || '';
                        }
                        if (DOM.instagramHandleInput) {
                            DOM.instagramHandleInput.value = config.instagram_handle || '';
                        }
                        if (DOM.writingStyleDisplay) {
                            _renderWritingStyleMarkdown(config.writing_style_ai || '');
                        }
                        if (DOM.psychologicalProfileDisplay) {
                            _renderPsychologicalProfileMarkdown(config.psychological_profile_ai || '');
                        }
                        if (DOM.systemInstructionsTextarea) {
                            DOM.systemInstructionsTextarea.value = config.system_instructions || '';
                        }
                        if (DOM.coreSystemInstructionsTextarea) {
                            DOM.coreSystemInstructionsTextarea.value = config.core_system_instructions || '';
                        }
                    } else {
                        // No config exists, load default from file
                        await loadDefaultInstructions();
                    }
                } catch (error) {
                    console.error('Error loading configuration:', error);
                    await loadDefaultInstructions();
                }
            } else {
                // First time setup - load default instructions from file
                await loadDefaultInstructions();
            }

            // Reset to first tab
            switchTab('system-instructions');
            
            Modals._openModal(DOM.subjectConfigurationModal);
        }

        async function loadDefaultInstructions() {
            // Try to load from API first (in case initialization already happened)
            try {
                const config = await loadConfiguration();
                if (config) {
                    if (DOM.systemInstructionsTextarea) {
                        DOM.systemInstructionsTextarea.value = config.system_instructions || '';
                    }
                    if (DOM.coreSystemInstructionsTextarea) {
                        DOM.coreSystemInstructionsTextarea.value = config.core_system_instructions || '';
                    }
                    if (DOM.writingStyleDisplay) {
                        _renderWritingStyleMarkdown(config.writing_style_ai || '');
                    }
                    if (DOM.psychologicalProfileDisplay) {
                        _renderPsychologicalProfileMarkdown(config.psychological_profile_ai || '');
                    }
                    return;
                }
            } catch (err) {
                console.debug('Could not load configuration from API:', err);
            }

            // Fallback to loading from files
            if (DOM.systemInstructionsTextarea && !DOM.systemInstructionsTextarea.value) {
                try {
                    const response = await fetch('/static/data/system_instructions_chat.txt');
                    if (response.ok) {
                        const text = await response.text();
                        if (DOM.systemInstructionsTextarea) {
                            DOM.systemInstructionsTextarea.value = text;
                        }
                    }
                } catch (err) {
                    console.debug('Could not load default system instructions:', err);
                }
            }

            if (DOM.coreSystemInstructionsTextarea && !DOM.coreSystemInstructionsTextarea.value) {
                try {
                    const response = await fetch('/static/data/system_instructions_core.txt');
                    if (response.ok) {
                        const text = await response.text();
                        if (DOM.coreSystemInstructionsTextarea) {
                            DOM.coreSystemInstructionsTextarea.value = text;
                        }
                    }
                } catch (err) {
                    console.debug('Could not load default core system instructions:', err);
                }
            }
        }

        function closeModal() {
            if (DOM.subjectConfigurationModal) {
                Modals._closeModal(DOM.subjectConfigurationModal);
            }
        }

        async function handleSave() {
            const subjectName = DOM.subjectNameInput ? DOM.subjectNameInput.value.trim() : '';
            const gender = DOM.subjectGenderSelect ? DOM.subjectGenderSelect.value : 'Male';
            const familyName = DOM.familyNameInput ? DOM.familyNameInput.value.trim() : '';
            const otherNames = DOM.otherNamesInput ? DOM.otherNamesInput.value.trim() : '';
            const emailAddresses = DOM.emailAddressesInput ? DOM.emailAddressesInput.value.trim() : '';
            const phoneNumbers = DOM.phoneNumbersInput ? DOM.phoneNumbersInput.value.trim() : '';
            const whatsappHandle = DOM.whatsappHandleInput ? DOM.whatsappHandleInput.value.trim() : '';
            const instagramHandle = DOM.instagramHandleInput ? DOM.instagramHandleInput.value.trim() : '';
            const systemInstructions = DOM.systemInstructionsTextarea ? DOM.systemInstructionsTextarea.value.trim() : '';

            if (!subjectName) {
                alert('Please enter a subject name');
                return;
            }

            if (!systemInstructions) {
                alert('Please enter system instructions');
                return;
            }

            try {
                await saveConfiguration(subjectName, systemInstructions, gender, familyName, otherNames, emailAddresses, phoneNumbers, whatsappHandle, instagramHandle);
                //updatePageReferences(subjectName, gender);
                closeModal();
                
                // Show success message
                alert('Subject configuration saved successfully!');
                
                // Reload page to ensure all references are updated
                window.location.reload();
            } catch (error) {
                alert(`Error saving configuration: ${error.message}`);
            }
        }

        function init() {
            // Set up event listeners
            if (DOM.saveSubjectConfigBtn) {
                DOM.saveSubjectConfigBtn.addEventListener('click', handleSave);
            }

            if (DOM.cancelSubjectConfigBtn) {
                DOM.cancelSubjectConfigBtn.addEventListener('click', () => {
                    if (!isInitialSetup) {
                        // Only allow cancel if not initial setup
                        closeModal();
                    }
                });
            }

            if (DOM.closeSubjectConfigModalBtn) {
                DOM.closeSubjectConfigModalBtn.addEventListener('click', () => {
                    if (!isInitialSetup) {
                        // Only allow close if not initial setup
                        closeModal();
                    }
                });
            }

            // Tab switching logic
            if (DOM.subjectConfigTabs && DOM.subjectConfigTabs.length > 0) {
                DOM.subjectConfigTabs.forEach(tab => {
                    tab.addEventListener('click', () => {
                        const tabName = tab.getAttribute('data-tab');
                        if (tabName) {
                            switchTab(tabName);
                        }
                    });
                });
            }

            // Writing style generate button
            if (DOM.requestWritingStyleBtn) {
                DOM.requestWritingStyleBtn.addEventListener('click', () => requestWritingStyle());
            }
            if (DOM.requestPsychologicalProfileBtn) {
                DOM.requestPsychologicalProfileBtn.addEventListener('click', () => requestPsychologicalProfile());
            }

            // Button in Settings tab to edit configuration
            const editSubjectConfigBtn = document.getElementById('edit-subject-config-btn');
            if (editSubjectConfigBtn) {
                editSubjectConfigBtn.addEventListener('click', () => {
                    showModal(true); // Load existing configuration
                });
            }

            // Prevent closing modal by clicking outside only during initial setup
            if (DOM.subjectConfigurationModal) {
                DOM.subjectConfigurationModal.addEventListener('click', (e) => {
                    if (e.target === DOM.subjectConfigurationModal && isInitialSetup) {
                        // Don't close - modal is non-dismissible during initial setup
                        e.stopPropagation();
                    } else if (e.target === DOM.subjectConfigurationModal && !isInitialSetup) {
                        // Allow closing when editing
                        closeModal();
                    }
                });
            }

            // Check and show modal on page load if needed
            checkAndShow();
        }

        return {
            init,
            checkAndShow,
            loadConfiguration,
            saveConfiguration,
            getSubjectName,
           // updatePageReferences,
            showModal,
            close: closeModal
        };
})();


Modals.ManageKeys = (() => {
    function _showStatus(msg, isError = false) {
        const el = document.getElementById('manage-keys-status');
        if (!el) return;
        el.textContent = msg;
        el.style.display = 'block';
        el.style.color = isError ? '#dc3545' : '#28a745';
        el.style.backgroundColor = isError ? 'rgba(220,53,69,0.1)' : 'rgba(40,167,69,0.1)';
    }

    function _closeCreateModal() {
        const modal = document.getElementById('create-trusted-key-modal');
        if (modal) modal.style.display = 'none';
        const userPw = document.getElementById('create-trusted-key-user-password');
        const masterPw = document.getElementById('create-trusted-key-master-password');
        const err = document.getElementById('create-trusted-key-error');
        if (userPw) userPw.value = '';
        if (masterPw) masterPw.value = '';
        if (err) { err.textContent = ''; err.style.display = 'none'; }
    }

    function _closeDeleteModal() {
        const modal = document.getElementById('delete-trusted-key-modal');
        if (modal) modal.style.display = 'none';
        const userPw = document.getElementById('delete-trusted-key-user-password');
        const masterPw = document.getElementById('delete-trusted-key-master-password');
        const err = document.getElementById('delete-trusted-key-error');
        if (userPw) userPw.value = '';
        if (masterPw) masterPw.value = '';
        if (err) { err.textContent = ''; err.style.display = 'none'; }
    }

    function _openCreateNewMasterKeyModal() {
        const modal = document.getElementById('create-new-master-key-modal');
        const step1 = document.getElementById('create-new-master-key-step1');
        const step2 = document.getElementById('create-new-master-key-step2');
        const cb1 = document.getElementById('create-master-key-understand-keys');
        const cb2 = document.getElementById('create-master-key-understand-data');
        const continueBtn = document.getElementById('create-new-master-key-continue');
        const pwInput = document.getElementById('create-new-master-key-password');
        const confirmInput = document.getElementById('create-new-master-key-confirm');
        const errEl = document.getElementById('create-new-master-key-error');
        if (modal) modal.style.display = 'flex';
        if (step1) step1.style.display = 'block';
        if (step2) step2.style.display = 'none';
        if (cb1) cb1.checked = false;
        if (cb2) cb2.checked = false;
        if (continueBtn) continueBtn.disabled = true;
        if (pwInput) pwInput.value = '';
        if (confirmInput) confirmInput.value = '';
        if (errEl) { errEl.textContent = ''; errEl.style.display = 'none'; }
    }

    function _closeCreateNewMasterKeyModal() {
        const modal = document.getElementById('create-new-master-key-modal');
        if (modal) modal.style.display = 'none';
    }

    function _createNewMasterKeyToStep2() {
        const step1 = document.getElementById('create-new-master-key-step1');
        const step2 = document.getElementById('create-new-master-key-step2');
        if (step1) step1.style.display = 'none';
        if (step2) step2.style.display = 'block';
    }

    function _createNewMasterKeyToStep1() {
        const step1 = document.getElementById('create-new-master-key-step1');
        const step2 = document.getElementById('create-new-master-key-step2');
        if (step1) step1.style.display = 'block';
        if (step2) step2.style.display = 'none';
        const errEl = document.getElementById('create-new-master-key-error');
        if (errEl) { errEl.textContent = ''; errEl.style.display = 'none'; }
    }

    async function _submitCreateNewMasterKey() {
        const pwInput = document.getElementById('create-new-master-key-password');
        const confirmInput = document.getElementById('create-new-master-key-confirm');
        const errEl = document.getElementById('create-new-master-key-error');
        const password = pwInput ? pwInput.value.trim() : '';
        const confirm = confirmInput ? confirmInput.value.trim() : '';
        if (!password) {
            if (errEl) { errEl.textContent = 'Please enter a password.'; errEl.style.display = 'block'; }
            return;
        }
        if (password !== confirm) {
            if (errEl) { errEl.textContent = 'Passwords do not match.'; errEl.style.display = 'block'; }
            return;
        }
        if (errEl) { errEl.textContent = ''; errEl.style.display = 'none'; }
        try {
            const resp = await fetch('/sensitive-data/master-key', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password })
            });
            const data = await resp.json().catch(() => ({}));
            if (!resp.ok) {
                throw new Error(data.detail || `HTTP ${resp.status}`);
            }
            _closeCreateNewMasterKeyModal();
            _showStatus(data.message || 'New master key created successfully.');
        } catch (e) {
            console.error('[ManageKeys] create new master key error:', e);
            if (errEl) { errEl.textContent = e.message || 'Failed to create master key.'; errEl.style.display = 'block'; }
        }
    }

    async function _createTrustedKey() {
        const userPw = document.getElementById('create-trusted-key-user-password');
        const masterPw = document.getElementById('create-trusted-key-master-password');
        const errEl = document.getElementById('create-trusted-key-error');
        const userPassword = userPw ? userPw.value.trim() : '';
        const masterPassword = masterPw ? masterPw.value.trim() : '';
        if (!userPassword) {
            if (errEl) { errEl.textContent = 'User password is required.'; errEl.style.display = 'block'; }
            return;
        }
        if (!masterPassword) {
            if (errEl) { errEl.textContent = 'Master password is required.'; errEl.style.display = 'block'; }
            return;
        }
        if (errEl) { errEl.textContent = ''; errEl.style.display = 'none'; }
        try {
            const resp = await fetch('/sensitive-data/trusted-key', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_password: userPassword, master_password: masterPassword })
            });
            const data = await resp.json().catch(() => ({}));
            if (!resp.ok) {
                throw new Error(data.detail || `HTTP ${resp.status}`);
            }
            _closeCreateModal();
            _showStatus(data.message || 'Trusted key created successfully.');
        } catch (e) {
            console.error('[ManageKeys] create error:', e);
            if (errEl) { errEl.textContent = e.message || 'Failed to create trusted key.'; errEl.style.display = 'block'; }
        }
    }

    async function _deleteTrustedKey() {
        const userPw = document.getElementById('delete-trusted-key-user-password');
        const masterPw = document.getElementById('delete-trusted-key-master-password');
        const errEl = document.getElementById('delete-trusted-key-error');
        const userPassword = userPw ? userPw.value.trim() : '';
        const masterPassword = masterPw ? masterPw.value.trim() : '';
        if (!userPassword) {
            if (errEl) { errEl.textContent = 'User password is required.'; errEl.style.display = 'block'; }
            return;
        }
        if (!masterPassword) {
            if (errEl) { errEl.textContent = 'Master password is required.'; errEl.style.display = 'block'; }
            return;
        }
        if (errEl) { errEl.textContent = ''; errEl.style.display = 'none'; }
        try {
            const resp = await fetch('/sensitive-data/trusted-key', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_password: userPassword, master_password: masterPassword })
            });
            const data = await resp.json().catch(() => ({}));
            if (!resp.ok) {
                throw new Error(data.detail || `HTTP ${resp.status}`);
            }
            _closeDeleteModal();
            _showStatus(data.message || 'Trusted key deleted successfully.');
        } catch (e) {
            console.error('[ManageKeys] delete error:', e);
            if (errEl) { errEl.textContent = e.message || 'Failed to delete trusted key.'; errEl.style.display = 'block'; }
        }
    }

    function init() {
        const createBtn = document.getElementById('create-trusted-key-btn');
        if (createBtn) createBtn.addEventListener('click', () => {
            const modal = document.getElementById('create-trusted-key-modal');
            if (modal) modal.style.display = 'flex';
        });

        const deleteBtn = document.getElementById('delete-trusted-key-btn');
        if (deleteBtn) deleteBtn.addEventListener('click', () => {
            const modal = document.getElementById('delete-trusted-key-modal');
            if (modal) modal.style.display = 'flex';
        });

        const closeCreate = document.getElementById('close-create-trusted-key-modal');
        if (closeCreate) closeCreate.addEventListener('click', _closeCreateModal);

        const closeDelete = document.getElementById('close-delete-trusted-key-modal');
        if (closeDelete) closeDelete.addEventListener('click', _closeDeleteModal);

        const cancelCreate = document.getElementById('create-trusted-key-cancel');
        if (cancelCreate) cancelCreate.addEventListener('click', _closeCreateModal);

        const cancelDelete = document.getElementById('delete-trusted-key-cancel');
        if (cancelDelete) cancelDelete.addEventListener('click', _closeDeleteModal);

        const submitCreate = document.getElementById('create-trusted-key-submit');
        if (submitCreate) submitCreate.addEventListener('click', _createTrustedKey);

        const submitDelete = document.getElementById('delete-trusted-key-submit');
        if (submitDelete) submitDelete.addEventListener('click', _deleteTrustedKey);

        const createModal = document.getElementById('create-trusted-key-modal');
        if (createModal) {
            createModal.addEventListener('click', e => {
                if (e.target === createModal) _closeCreateModal();
            });
        }

        const deleteModal = document.getElementById('delete-trusted-key-modal');
        if (deleteModal) {
            deleteModal.addEventListener('click', e => {
                if (e.target === deleteModal) _closeDeleteModal();
            });
        }

        // Create New Master Key
        const createNewMasterKeyBtn = document.getElementById('create-new-master-key-btn');
        if (createNewMasterKeyBtn) createNewMasterKeyBtn.addEventListener('click', _openCreateNewMasterKeyModal);

        const closeCreateNewMasterKeyBtn = document.getElementById('close-create-new-master-key-modal');
        if (closeCreateNewMasterKeyBtn) closeCreateNewMasterKeyBtn.addEventListener('click', _closeCreateNewMasterKeyModal);

        const cancelCreateNewMasterKeyBtn = document.getElementById('create-new-master-key-cancel');
        if (cancelCreateNewMasterKeyBtn) cancelCreateNewMasterKeyBtn.addEventListener('click', _closeCreateNewMasterKeyModal);

        const cbUnderstandKeys = document.getElementById('create-master-key-understand-keys');
        const cbUnderstandData = document.getElementById('create-master-key-understand-data');
        const continueNewMasterKeyBtn = document.getElementById('create-new-master-key-continue');
        function _updateContinueEnabled() {
            if (continueNewMasterKeyBtn) {
                continueNewMasterKeyBtn.disabled = !(cbUnderstandKeys && cbUnderstandKeys.checked && cbUnderstandData && cbUnderstandData.checked);
            }
        }
        if (cbUnderstandKeys) cbUnderstandKeys.addEventListener('change', _updateContinueEnabled);
        if (cbUnderstandData) cbUnderstandData.addEventListener('change', _updateContinueEnabled);

        if (continueNewMasterKeyBtn) continueNewMasterKeyBtn.addEventListener('click', _createNewMasterKeyToStep2);

        const backNewMasterKeyBtn = document.getElementById('create-new-master-key-back');
        if (backNewMasterKeyBtn) backNewMasterKeyBtn.addEventListener('click', _createNewMasterKeyToStep1);

        const submitNewMasterKeyBtn = document.getElementById('create-new-master-key-submit');
        if (submitNewMasterKeyBtn) submitNewMasterKeyBtn.addEventListener('click', _submitCreateNewMasterKey);

        const createNewMasterKeyModal = document.getElementById('create-new-master-key-modal');
        if (createNewMasterKeyModal) {
            createNewMasterKeyModal.addEventListener('click', e => {
                if (e.target === createNewMasterKeyModal) _closeCreateNewMasterKeyModal();
            });
        }

        const pwToggleNew = document.getElementById('create-new-master-key-password-toggle');
        if (pwToggleNew) {
            pwToggleNew.addEventListener('click', () => {
                const inp = document.getElementById('create-new-master-key-password');
                if (!inp) return;
                const isPassword = inp.type === 'password';
                inp.type = isPassword ? 'text' : 'password';
                pwToggleNew.innerHTML = isPassword ? '<i class="fas fa-eye-slash"></i>' : '<i class="fas fa-eye"></i>';
                pwToggleNew.title = isPassword ? 'Hide password' : 'Show password';
            });
        }
        const confirmToggleNew = document.getElementById('create-new-master-key-confirm-toggle');
        if (confirmToggleNew) {
            confirmToggleNew.addEventListener('click', () => {
                const inp = document.getElementById('create-new-master-key-confirm');
                if (!inp) return;
                const isPassword = inp.type === 'password';
                inp.type = isPassword ? 'text' : 'password';
                confirmToggleNew.innerHTML = isPassword ? '<i class="fas fa-eye-slash"></i>' : '<i class="fas fa-eye"></i>';
                confirmToggleNew.title = isPassword ? 'Hide password' : 'Show password';
            });
        }

        const pwInputNew = document.getElementById('create-new-master-key-password');
        const confirmInputNew = document.getElementById('create-new-master-key-confirm');
        const enterHandler = e => { if (e.key === 'Enter') _submitCreateNewMasterKey(); };
        if (pwInputNew) pwInputNew.addEventListener('keydown', enterHandler);
        if (confirmInputNew) confirmInputNew.addEventListener('keydown', enterHandler);
    }

    return { init };
})();


Modals.initAll = () => {
        Modals.Suggestions.init();
        Modals.FBAlbums.init();
        Modals.ImageDetailModal.init();
        Modals.MultiImageDisplay.init();
        //Modals.HaveYourSay.init();
        Modals.Locations.init();
        // Modals.ImageGallery.init();
        Modals.EmailGallery.init();
        Modals.EmailEditor.init();
        Modals.NewImageGallery.init();
        Modals.SMSMessages.init();
        Modals.SingleImageDisplay.init();
        Modals.ReferenceDocuments.init();
        Modals.Contacts.init();
        Modals.Relationships.init();
        Modals.ConfirmationModal.init();
        Modals.ConversationSummary.init();
        Modals.AddInterviewee.init();
        Modals.ReferenceDocumentsNotification.init();
        Modals.ConversationManager.init();
        Modals.SubjectConfiguration.init();
        Modals.Artefacts.init();
        Modals.SensitiveData.init();
        Modals.ManageKeys.init();
        Modals.Profiles.init();
};

Modals.closeAll = () => {
        // Close all modals that have a close function
        try {
            if (Modals.Suggestions && Modals.Suggestions.close) Modals.Suggestions.close();
        } catch (e) { console.debug('Error closing Suggestions modal:', e); }
        
        try {
            if (Modals.FBAlbums && Modals.FBAlbums.close) Modals.FBAlbums.close();
        } catch (e) { console.debug('Error closing FBAlbums modal:', e); }
        
        try {
            if (Modals.EmailGallery && Modals.EmailGallery.close) Modals.EmailGallery.close();
        } catch (e) { console.debug('Error closing EmailGallery modal:', e); }
        
        try {
            if (Modals.EmailEditor && Modals.EmailEditor.close) Modals.EmailEditor.close();
        } catch (e) { console.debug('Error closing EmailEditor modal:', e); }
        
        try {
            if (Modals.NewImageGallery && Modals.NewImageGallery.close) Modals.NewImageGallery.close();
        } catch (e) { console.debug('Error closing NewImageGallery modal:', e); }
        
        try {
            if (Modals.ImageDetailModal && Modals.ImageDetailModal.close) Modals.ImageDetailModal.close();
        } catch (e) { console.debug('Error closing ImageDetailModal:', e); }
        
        try {
            if (Modals.ConversationSummary && Modals.ConversationSummary.close) Modals.ConversationSummary.close();
        } catch (e) { console.debug('Error closing ConversationSummary modal:', e); }
        
        try {
            if (Modals.SMSMessages && Modals.SMSMessages.close) Modals.SMSMessages.close();
        } catch (e) { console.debug('Error closing SMSMessages modal:', e); }
        
        try {
            if (Modals.AddInterviewee && Modals.AddInterviewee.close) Modals.AddInterviewee.close();
        } catch (e) { console.debug('Error closing AddInterviewee modal:', e); }
        
        try {
            if (Modals.ReferenceDocuments && Modals.ReferenceDocuments.close) Modals.ReferenceDocuments.close();
        } catch (e) { console.debug('Error closing ReferenceDocuments modal:', e); }
        
        try {
            if (Modals.Contacts && Modals.Contacts.close) Modals.Contacts.close();
        } catch (e) { console.debug('Error closing Contacts modal:', e); }
        
        try {
            if (Modals.Profiles && Modals.Profiles.close) Modals.Profiles.close();
        } catch (e) { console.debug('Error closing Profiles modal:', e); }
        
        try {
            if (Modals.Relationships && Modals.Relationships.close) Modals.Relationships.close();
        } catch (e) { console.debug('Error closing Relationships modal:', e); }
        
        try {
            if (Modals.Locations && Modals.Locations.close) Modals.Locations.close();
        } catch (e) { console.debug('Error closing Locations modal:', e); }
        
        try {
            if (Modals.ConfirmationModal && Modals.ConfirmationModal.close) Modals.ConfirmationModal.close();
        } catch (e) { console.debug('Error closing ConfirmationModal:', e); }
        
        // Close SingleImageDisplay modal directly via DOM
        try {
            if (DOM.singleImageModal) {
                Modals._closeModal(DOM.singleImageModal);
            }
        } catch (e) { console.debug('Error closing SingleImageDisplay modal:', e); }
        
        // Close MultiImageDisplay modal if it exists
        try {
            const multiImageModal = document.getElementById('multi-image-modal');
            if (multiImageModal) {
                Modals._closeModal(multiImageModal);
            }
        } catch (e) { console.debug('Error closing MultiImageDisplay modal:', e); }
        
        // Also close any other modals by checking DOM elements with modal class
        try {
            const allModals = document.querySelectorAll('.modal, [class*="modal"], [id*="modal"], [id*="Modal"]');
            allModals.forEach(modal => {
                if (modal && modal.style) {
                    const display = window.getComputedStyle(modal).display;
                    if (display === 'flex' || display === 'block') {
                        modal.style.display = 'none';
                    }
                }
            });
        } catch (e) { console.debug('Error closing modals via DOM query:', e); }
    };

