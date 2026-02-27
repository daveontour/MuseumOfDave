'use strict';

const AppActions = {
    // [CONSTANTS.FUNCTION_NAMES.FirstFunction]: async () => { // getFacebookChatters
    //     UI.clearError();
    //     DOM.infoBox.classList.add('hidden');
    //     UI.setControlsEnabled(false);
    //     UI.showLoadingIndicator();
    //     try {
    //         const data = await ApiService.fetchFacebookChatters();
    //         let markdownText = '# Facebook Chat Statistics\n\n|Participant|Number of Messages|\n|-----|---|\n';
    //         for (const message of Object.values(data)) { // Iterate over values if data is an object
    //             markdownText += `| ${message.participant[0].name} |${message.number_of_messages}|\n`;
    //         }
    //         Chat.addMessage('assistant', markdownText, true);
    //     } catch (error) {
    //         console.error('Error in getFacebookChatters:', error);
    //         UI.displayError("Failed to get FB chatters: " + error.message);
    //     } finally {
    //         UI.setControlsEnabled(true);
    //         UI.hideLoadingIndicator();
    //     }
    // },
    ["showFBAlbumsOptions"]: () => Modals.FBAlbums.open(),    // showFBAlbumsOptions
    ["openGeoModal"]: () => Modals.Locations.open(), // showGeoMetadataOptions
    ["showEmailGallery"]: () => Modals.EmailGallery.open(), // showEmailGalleryOptions
    //[CONSTANTS.FUNCTION_NAMES.FifthFunction]: () => SSE.browserFunctions.showLocationInfo(), // showTileAlbumOptions
    ["showImageGallery"]: () => Modals.ImageGallery.open(),
    //[CONSTANTS.FUNCTION_NAMES.SeventhFunction]: () => SSE.browserFunctions.testEmail(), // showImageGalleryOptions
 // showEmailGalleryOptions
    ["listContacts"]: () => Modals.Contacts.open(),

};
window.customObject = AppActions; // Expose for Suggestions.json if it relies on global `customObject`

const App = (() => {
    async function processFormSubmit(userPrompt, category = null, title = null, supplementary_prompt = null) {
        if (!userPrompt && !category && !title) return;

        // Check and show reference documents notification before proceeding
        await Modals.ReferenceDocumentsNotification.checkAndShow(async () => {
            // This callback is called when user proceeds
            UI.clearError();
            UI.setControlsEnabled(false);
            UI.showLoadingIndicator();

            const selectedVoice = VoiceSelector.getSelectedVoice();
            const selectedMood = (selectedVoice === 'owner' && DOM.ownerMood) ? DOM.ownerMood.value : null;
            
            try {
                const finalMessage = UI.getWorkModePrefix() + userPrompt;

                if (category && title) Chat.addMessage('suggestion', `**${category}:** ${title}`, true);
                else Chat.addMessage('user', userPrompt, false); // User messages are not markdown by default
                
                DOM.userInput.value = '';

                const currentUserId = localStorage.getItem('userId') || 'default';
                // Get current conversation ID if available
                const conversationId = Modals.ConversationManager ? Modals.ConversationManager.getCurrentConversationId() : null;
                
                const response = await ApiService.fetchChat({
                    prompt: finalMessage,
                    voice: selectedVoice,
                    mood: selectedMood,
                    interviewMode: AppState.isInterviewerMode, // Use interviewer mode state instead of checkbox
                    companionMode: DOM.companionModeCheckbox ? DOM.companionModeCheckbox.checked : false,
                    supplementary_prompt: supplementary_prompt,
                    temperature: parseFloat(DOM.creativityLevel ? DOM.creativityLevel.value : '0'),
                    conversation_id: conversationId,
                    clientId: AppState.clientId,
                    userId:currentUserId
                });
                
                // Non-streaming JSON response handling (original code commented out streaming)
                const data = await response.json();
                UI.hideLoadingIndicator(); // Hide after getting response, before adding message
                if (data.error) UI.displayError(data.error);
                else Chat.addMessage('assistant', data.response, true, null, data.embedded_json);

            } catch (error) {
                console.error('Form submit error:', error);
                UI.displayError(error.message || 'An unknown error occurred.');
                // UI.hideLoadingIndicator(); // Already handled in displayError or finally
            } finally {
                UI.setControlsEnabled(true);
                UI.hideLoadingIndicator(); // Ensure it's hidden
            }
        });
    }

    function initEventListeners() {
        DOM.chatForm.addEventListener('submit', (event) => {
            event.preventDefault();
            const userPrompt = DOM.userInput.value.trim();
            if (!userPrompt) return;
            processFormSubmit(userPrompt);
        });
        
        // Resume Conversation button
        if (DOM.resumeConversationBtn) {
            DOM.resumeConversationBtn.addEventListener('click', () => {
                Modals.ConversationManager.showConversationList();
            });
        }

        DOM.userInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                // dispatchEvent on form seems more robust than calling submit() directly
                DOM.chatForm.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
            }
        });

        // Hamburger menu for config page
        DOM.hamburgerMenu.addEventListener('click', () => {
            DOM.configPage.style.display = 'block';
            DOM.chatMain.style.display = 'none';
            loadControlDefaults();
        });
        DOM.closeConfigBtn.addEventListener('click', () => {
            DOM.configPage.style.display = 'none';
            DOM.chatMain.style.display = 'flex';
        });

        // Load control defaults from API
        let controlDefaults = {};
        let controlDefaultsListenersSetup = false;
        
        async function loadControlDefaults() {
            try {
                const response = await fetch('/api/control-defaults');
                if (response.ok) {
                    controlDefaults = await response.json();
                    populateControlDefaults();
                    if (!controlDefaultsListenersSetup) {
                        setupControlDefaultsListeners();
                        controlDefaultsListenersSetup = true;
                    }
                }
            } catch (error) {
                console.error('Error loading control defaults:', error);
            }
        }

        // Helper function to get value from localStorage or defaults
        function getControlValue(key, defaultValue) {
            const stored = localStorage.getItem(`control_defaults_${key}`);
            if (stored !== null) {
                // Try to parse as boolean or number, otherwise return as string
                if (stored === 'true') return true;
                if (stored === 'false') return false;
                if (!isNaN(stored) && stored !== '') return stored; // Return as string for numbers
                return stored;
            }
            return defaultValue;
        }

        // Helper function to save value to localStorage
        function saveControlValue(key, value) {
            if (value === null || value === undefined) {
                localStorage.removeItem(`control_defaults_${key}`);
            } else {
                localStorage.setItem(`control_defaults_${key}`, String(value));
            }
        }

        // Populate control inputs with localStorage values (preferred) or defaults
        function populateControlDefaults() {
            // Email Controls
            const processAllFoldersCheckbox = document.getElementById('process-all-folders');
            const newOnlyOption = document.getElementById('new-only-option');
            if (processAllFoldersCheckbox) {
                const value = getControlValue('process_all_folders', controlDefaults.process_all_folders);
                if (value !== undefined && value !== null) {
                    processAllFoldersCheckbox.checked = value === true || value === 'true';
                }
            }
            if (newOnlyOption) {
                const value = getControlValue('new_only_option', controlDefaults.new_only_option);
                if (value !== undefined && value !== null) {
                    newOnlyOption.checked = value === true || value === 'true';
                }
            }

            // WhatsApp Import
            const whatsappImportDirectory = document.getElementById('whatsapp-import-directory');
            if (whatsappImportDirectory) {
                const value = getControlValue('whatsapp_import_directory', controlDefaults.whatsapp_import_directory);
                if (value) {
                    whatsappImportDirectory.value = value;
                }
            }

            // Facebook Messenger Import
            const facebookImportDirectory = document.getElementById('facebook-import-directory');
            const facebookUserName = document.getElementById('facebook-user-name');
            if (facebookImportDirectory) {
                const value = getControlValue('facebook_import_directory', controlDefaults.facebook_import_directory);
                if (value) {
                    facebookImportDirectory.value = value;
                }
            }
            if (facebookUserName) {
                const value = getControlValue('facebook_user_name', controlDefaults.facebook_user_name);
                if (value) {
                    facebookUserName.value = value;
                }
            }

            // Instagram Import
            const instagramImportDirectory = document.getElementById('instagram-import-directory');
            const instagramUserName = document.getElementById('instagram-user-name');
            if (instagramImportDirectory) {
                const value = getControlValue('instagram_import_directory', controlDefaults.instagram_import_directory);
                if (value) {
                    instagramImportDirectory.value = value;
                }
            }
            if (instagramUserName) {
                const value = getControlValue('instagram_user_name', controlDefaults.instagram_user_name);
                if (value) {
                    instagramUserName.value = value;
                }
            }

            // iMessage Import
            const imessageDirectoryPath = document.getElementById('imessage-directory-path');
            if (imessageDirectoryPath) {
                const value = getControlValue('imessage_directory_path', controlDefaults.imessage_directory_path);
                if (value) {
                    imessageDirectoryPath.value = value;
                }
            }

            // Facebook Albums Import
            const facebookAlbumsImportDirectory = document.getElementById('facebook-albums-import-directory');
            if (facebookAlbumsImportDirectory) {
                const value = getControlValue('facebook_albums_import_directory', controlDefaults.facebook_albums_import_directory);
                if (value) {
                    facebookAlbumsImportDirectory.value = value;
                }
            }

            // Filesystem Image Import
            const filesystemImportDirectory = document.getElementById('filesystem-import-directory');
            const filesystemImportMaxImages = document.getElementById('filesystem-import-max-images');
            if (filesystemImportDirectory) {
                const value = getControlValue('filesystem_import_directory', controlDefaults.filesystem_import_directory);
                if (value) {
                    filesystemImportDirectory.value = value;
                }
            }
            if (filesystemImportMaxImages) {
                const value = getControlValue('filesystem_import_max_images', controlDefaults.filesystem_import_max_images);
                if (value) {
                    filesystemImportMaxImages.value = value;
                }
            }
        }

        // Setup event listeners to save changes to localStorage
        function setupControlDefaultsListeners() {
            // Email Controls
            const processAllFoldersCheckbox = document.getElementById('process-all-folders');
            const newOnlyOption = document.getElementById('new-only-option');
            if (processAllFoldersCheckbox) {
                processAllFoldersCheckbox.addEventListener('change', (e) => {
                    saveControlValue('process_all_folders', e.target.checked);
                });
            }
            if (newOnlyOption) {
                newOnlyOption.addEventListener('change', (e) => {
                    saveControlValue('new_only_option', e.target.checked);
                });
            }

            // WhatsApp Import
            const whatsappImportDirectory = document.getElementById('whatsapp-import-directory');
            if (whatsappImportDirectory) {
                whatsappImportDirectory.addEventListener('change', (e) => {
                    saveControlValue('whatsapp_import_directory', e.target.value);
                });
                whatsappImportDirectory.addEventListener('blur', (e) => {
                    saveControlValue('whatsapp_import_directory', e.target.value);
                });
            }

            // Facebook Messenger Import
            const facebookImportDirectory = document.getElementById('facebook-import-directory');
            const facebookUserName = document.getElementById('facebook-user-name');
            if (facebookImportDirectory) {
                facebookImportDirectory.addEventListener('change', (e) => {
                    saveControlValue('facebook_import_directory', e.target.value);
                });
                facebookImportDirectory.addEventListener('blur', (e) => {
                    saveControlValue('facebook_import_directory', e.target.value);
                });
            }
            if (facebookUserName) {
                facebookUserName.addEventListener('change', (e) => {
                    saveControlValue('facebook_user_name', e.target.value);
                });
                facebookUserName.addEventListener('blur', (e) => {
                    saveControlValue('facebook_user_name', e.target.value);
                });
            }

            // Instagram Import
            const instagramImportDirectory = document.getElementById('instagram-import-directory');
            const instagramUserName = document.getElementById('instagram-user-name');
            if (instagramImportDirectory) {
                instagramImportDirectory.addEventListener('change', (e) => {
                    saveControlValue('instagram_import_directory', e.target.value);
                });
                instagramImportDirectory.addEventListener('blur', (e) => {
                    saveControlValue('instagram_import_directory', e.target.value);
                });
            }
            if (instagramUserName) {
                instagramUserName.addEventListener('change', (e) => {
                    saveControlValue('instagram_user_name', e.target.value);
                });
                instagramUserName.addEventListener('blur', (e) => {
                    saveControlValue('instagram_user_name', e.target.value);
                });
            }

            // iMessage Import
            const imessageDirectoryPath = document.getElementById('imessage-directory-path');
            if (imessageDirectoryPath) {
                imessageDirectoryPath.addEventListener('change', (e) => {
                    saveControlValue('imessage_directory_path', e.target.value);
                });
                imessageDirectoryPath.addEventListener('blur', (e) => {
                    saveControlValue('imessage_directory_path', e.target.value);
                });
            }

            // Facebook Albums Import
            const facebookAlbumsImportDirectory = document.getElementById('facebook-albums-import-directory');
            if (facebookAlbumsImportDirectory) {
                facebookAlbumsImportDirectory.addEventListener('change', (e) => {
                    saveControlValue('facebook_albums_import_directory', e.target.value);
                });
                facebookAlbumsImportDirectory.addEventListener('blur', (e) => {
                    saveControlValue('facebook_albums_import_directory', e.target.value);
                });
            }

            // Filesystem Image Import
            const filesystemImportDirectory = document.getElementById('filesystem-import-directory');
            const filesystemImportMaxImages = document.getElementById('filesystem-import-max-images');
            if (filesystemImportDirectory) {
                filesystemImportDirectory.addEventListener('change', (e) => {
                    saveControlValue('filesystem_import_directory', e.target.value);
                });
                filesystemImportDirectory.addEventListener('blur', (e) => {
                    saveControlValue('filesystem_import_directory', e.target.value);
                });
            }
            if (filesystemImportMaxImages) {
                filesystemImportMaxImages.addEventListener('change', (e) => {
                    saveControlValue('filesystem_import_max_images', e.target.value);
                });
                filesystemImportMaxImages.addEventListener('blur', (e) => {
                    saveControlValue('filesystem_import_max_images', e.target.value);
                });
            }
        }

        // Load defaults when config page opens
        const configBtn = document.getElementById('config-btn');
        if (configBtn) {
            configBtn.addEventListener('click', () => {
                loadControlDefaults();
            });
        }

        // Config tab switching
        const configTabButtons = document.querySelectorAll('.config-tab-button');
        const configTabContents = document.querySelectorAll('.config-tab-content');
        
        configTabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const targetTab = button.getAttribute('data-tab');
                
                // Remove active class from all buttons and contents
                configTabButtons.forEach(btn => btn.classList.remove('active'));
                configTabContents.forEach(content => content.classList.remove('active'));
                
                // Add active class to clicked button and corresponding content
                button.classList.add('active');
                const targetContent = document.getElementById(`${targetTab}-tab`);
                    if (targetContent) {
                    targetContent.classList.add('active');
                }
                
                // Initialize images grid when images-grid tab is opened
                if (targetTab === 'images-grid') {
                    // Check if loadImages function exists and call it
                    if (typeof loadImages === 'function') {
                        setTimeout(() => {
                            const imagesGrid = document.getElementById('images-grid');
                            if (imagesGrid && (imagesGrid.innerHTML === '' || imagesGrid.style.display === 'none')) {
                                loadImages(1);
                            }
                        }, 100);
                    }
                }
                
                // Load control defaults when any control tab is opened (if not already loaded)
                const controlTabs = ['import-controls'];
                if (controlTabs.includes(targetTab) && Object.keys(controlDefaults).length === 0) {
                    loadControlDefaults();
                } else if (controlTabs.includes(targetTab)) {
                    // If defaults already loaded, just populate (in case elements weren't ready before)
                    populateControlDefaults();
                }
                // Load last run times when Import Controls tab is opened
                if (targetTab === 'import-controls') {
                    loadImportControlLastRun();
                }
            });
        });

        // Format date/time in local timezone, 24-hour format (dd/mm/yyyy HH:mm)
        function formatImportLastRunLocal(isoString) {
            if (!isoString) return '';
            try {
                const date = new Date(isoString);
                if (isNaN(date.getTime())) return '';
                return new Intl.DateTimeFormat('en-AU', {
                    day: '2-digit',
                    month: '2-digit',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: false
                }).format(date);
            } catch (e) {
                return '';
            }
        }

        async function loadImportControlLastRun() {
            try {
                const response = await fetch('/api/import-control-last-run');
                if (!response.ok) return;
                const data = await response.json();
                const mapping = {
                    email_processing: 'import-last-run-email_processing',
                    whatsapp: 'import-last-run-whatsapp',
                    facebook: 'import-last-run-facebook',
                    instagram: 'import-last-run-instagram',
                    imessage: 'import-last-run-imessage',
                    facebook_albums: 'import-last-run-facebook_albums',
                    facebook_places: 'import-last-run-facebook_places',
                    filesystem: 'import-last-run-filesystem',
                    thumbnails: 'import-last-run-thumbnails',
                    contacts: 'import-last-run-contacts'
                };
                for (const [importType, elementId] of Object.entries(mapping)) {
                    const el = document.getElementById(elementId);
                    if (!el) continue;
                    const info = data[importType];
                    if (!info || !info.last_run_at) {
                        el.textContent = '';
                        continue;
                    }
                    const formatted = formatImportLastRunLocal(info.last_run_at);
                    const resultLabel = (info.result === 'success' || info.result === 'completed') ? 'success' : (info.result === 'cancelled' ? 'cancelled' : 'error');
                    el.textContent = `Last run: ${formatted} (${resultLabel})`;
                    el.title = info.result_message || '';
                }
            } catch (e) {
                console.warn('Failed to load import control last run:', e);
            }
        }

        // Empty Media Tables Button
        const emptyMediaTablesBtn = document.getElementById('empty-media-tables-btn');
        const emptyTablesStatus = document.getElementById('empty-tables-status');
        
        if (emptyMediaTablesBtn) {
            emptyMediaTablesBtn.addEventListener('click', async () => {
                // Show confirmation dialog
                const confirmed = confirm(
                    'WARNING: This will permanently delete ALL data from:\n\n' +
                    '- attachments\n' +
                    '- media_blob\n' +
                    '- media_items\n' +
                    '- messages\n' +
                    '- message_attachments\n\n' +
                    'This action cannot be undone!\n\n' +
                    'Are you absolutely sure you want to continue?'
                );
                
                if (!confirmed) {
                    return;
                }
                
                //Double confirmation
                const doubleConfirmed = confirm(
                    'FINAL WARNING: This will DELETE ALL messages and media data.\n\n' 
                );
                
                if (!doubleConfirmed) {
                    return;
                }
                const userInput = "DELETE";
               // const userInput = prompt('Type "DELETE" to confirm:');
                if (userInput !== 'DELETE') {
                    if (emptyTablesStatus) {
                        emptyTablesStatus.style.display = 'block';
                        emptyTablesStatus.style.backgroundColor = '#fff3cd';
                        emptyTablesStatus.style.color = '#856404';
                        emptyTablesStatus.style.border = '1px solid #ffc107';
                        emptyTablesStatus.textContent = 'Operation cancelled. Tables were not emptied.';
                    }
                    return;
                }
                
                // Disable button and show loading
                emptyMediaTablesBtn.disabled = true;
                emptyMediaTablesBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Emptying tables...';
                
                if (emptyTablesStatus) {
                    emptyTablesStatus.style.display = 'block';
                    emptyTablesStatus.style.backgroundColor = '#d1ecf1';
                    emptyTablesStatus.style.color = '#0c5460';
                    emptyTablesStatus.style.border = '1px solid #bee5eb';
                    emptyTablesStatus.textContent = 'Emptying tables...';
                }
                
                try {
                    const response = await fetch('/admin/empty-media-tables', {
                        method: 'DELETE'
                    });
                    
                    if (!response.ok) {
                        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
                        throw new Error(errorData.detail || `HTTP ${response.status}`);
                    }
                    
                    const result = await response.json();
                    
                    // Show success message
                    if (emptyTablesStatus) {
                        emptyTablesStatus.style.backgroundColor = '#d4edda';
                        emptyTablesStatus.style.color = '#155724';
                        emptyTablesStatus.style.border = '1px solid #c3e6cb';
                        
                        const counts = result.deleted_counts || {};
                        emptyTablesStatus.innerHTML = `
                            <strong>Tables emptied successfully!</strong><br>
                            Deleted counts:<br>
                            • Messages: ${counts.messages || 0}<br>
                            • Message Attachments: ${counts.message_attachments || 0}<br>
                            • Media Items: ${counts.media_items || 0}<br>
                            • Media Blobs: ${counts.media_blob || 0}<br>
                            • Attachments: ${counts.attachments || 0}<br>
                            • Facebook Album Images: ${counts.facebook_album_images || 0}<br>
                            • Facebook Albums: ${counts.facebook_albums || 0}<br>
                        `;
                    }
                    
                    // Re-enable button
                    emptyMediaTablesBtn.disabled = false;
                    emptyMediaTablesBtn.innerHTML = '<i class="fas fa-trash-alt"></i> Empty Media and Message Tables';
                    
                } catch (error) {
                    console.error('Error emptying tables:', error);
                    
                    if (emptyTablesStatus) {
                        emptyTablesStatus.style.backgroundColor = '#f8d7da';
                        emptyTablesStatus.style.color = '#721c24';
                        emptyTablesStatus.style.border = '1px solid #f5c6cb';
                        emptyTablesStatus.textContent = `Error: ${error.message}`;
                    }
                    
                    // Re-enable button
                    emptyMediaTablesBtn.disabled = false;
                    emptyMediaTablesBtn.innerHTML = '<i class="fas fa-trash-alt"></i> Empty Media and Message Tables';
                }
            });
        }

        // Email Processing Controls
        const processAllFoldersCheckbox = document.getElementById('process-all-folders');
        const folderSelect = document.getElementById('folder-select');
        const folderSelectionGroup = document.getElementById('folder-selection-group');
        const newOnlyOption = document.getElementById('new-only-option');
        const startProcessingBtn = document.getElementById('start-processing-btn');
        const cancelProcessingBtn = document.getElementById('cancel-processing-btn');
        const processingStatus = document.getElementById('processing-status');
        const processingStatusMessage = document.getElementById('processing-status-message');
        const processingStatusDetails = document.getElementById('processing-status-details');
        const processingProgressContainer = document.getElementById('processing-progress-container');
        const currentLabelName = document.getElementById('current-label-name');
        const labelProgressText = document.getElementById('label-progress-text');
        const processingProgressBar = document.getElementById('processing-progress-bar');
        const progressBarText = document.getElementById('progress-bar-text');
        const emailsProcessedCount = document.getElementById('emails-processed-count');
        let eventSource = null;

        // Toggle folder selection based on "Process All" checkbox
        if (processAllFoldersCheckbox) {
            // Set initial state
            if (processAllFoldersCheckbox.checked) {
                folderSelectionGroup.style.display = 'none';
            }
            
            processAllFoldersCheckbox.addEventListener('change', (e) => {
                if (e.target.checked) {
                    folderSelectionGroup.style.display = 'none';
                } else {
                    folderSelectionGroup.style.display = 'block';
                }
            });
        }

        // Load folders from API
        async function loadFolders() {
            if (!folderSelect) return;
            
            try {
                const response = await fetch('/emails/folders');
                if (!response.ok) {
                    throw new Error(`Failed to load folders: ${response.statusText}`);
                }
                const folders = await response.json();
                
                folderSelect.innerHTML = '';
                folders.forEach(folder => {
                    const option = document.createElement('option');
                    option.value = folder.name;
                    option.textContent = folder.name;
                    folderSelect.appendChild(option);
                });
            } catch (error) {
                folderSelect.innerHTML = '<option value="">Error loading folders</option>';
                showProcessingStatus('error', 'Failed to load folders', error.message);
            }
        }

        // Close SSE connection if open
        function closeEventSource() {
            if (eventSource) {
                eventSource.close();
                eventSource = null;
            }
        }

        // Request browser notification permission
        async function requestNotificationPermission() {
            if ('Notification' in window && Notification.permission === 'default') {
                await Notification.requestPermission();
            }
        }

        // Show browser notification
        function showNotification(title, body, icon = null) {
            if ('Notification' in window && Notification.permission === 'granted') {
                new Notification(title, {
                    body: body,
                    icon: icon || '/static/images/expert.png',
                    tag: 'email-processing'
                });
            }
        }

        // Update progress display
        function updateProgressDisplay(progressData) {
            if (!processingProgressContainer) return;

            const {
                current_label,
                current_label_index,
                total_labels,
                emails_processed,
                status
            } = progressData;

            // Show progress container when processing starts
            if (status === 'in_progress') {
                processingProgressContainer.style.display = 'block';
            }

            // Update current label
            if (currentLabelName) {
                currentLabelName.textContent = current_label || 'Waiting...';
            }

            // Update label progress
            if (labelProgressText) {
                labelProgressText.textContent = `${current_label_index} / ${total_labels}`;
            }

            // Update progress bar
            if (total_labels > 0 && processingProgressBar && progressBarText) {
                const percentage = Math.round((current_label_index / total_labels) * 100);
                processingProgressBar.style.width = `${percentage}%`;
                progressBarText.textContent = `${percentage}%`;
            }

            // Update emails processed count
            if (emailsProcessedCount) {
                emailsProcessedCount.textContent = emails_processed || 0;
            }
        }

        // Connect to SSE stream
        function connectToProgressStream() {
            // Close existing connection if any
            closeEventSource();

            // Request notification permission
            requestNotificationPermission();

            // Create EventSource connection
            eventSource = new EventSource('/emails/process/stream');

            eventSource.onmessage = (event) => {
                try {
                    const eventData = JSON.parse(event.data);
                    handleProgressEvent(eventData);
                } catch (error) {
                    console.error('Error parsing SSE event:', error);
                }
            };

            eventSource.onerror = (error) => {
                console.error('SSE connection error:', error);
                // Don't close on error - EventSource will attempt to reconnect
            };

            // Clean up on page unload
            window.addEventListener('beforeunload', () => {
                closeEventSource();
            });
        }

        // Handle progress events from SSE
        function handleProgressEvent(eventData) {
            const { type, data } = eventData;

            switch (type) {
                case 'progress':
                    updateProgressDisplay(data);
                    if (data.status === 'in_progress') {
                        cancelProcessingBtn.style.display = 'inline-block';
                        startProcessingBtn.disabled = true;
                        showProcessingStatus('info', 'Processing in progress...', `Processing label ${data.current_label_index} of ${data.total_labels}`);
                    }
                    break;

                case 'completed':
                    updateProgressDisplay(data);
                    cancelProcessingBtn.style.display = 'none';
                    startProcessingBtn.disabled = false;
                    showProcessingStatus('success', 'Processing completed', `Successfully processed ${data.emails_processed} emails from ${data.total_labels} label(s).`);
                    showNotification('Email Processing Complete', `Processed ${data.emails_processed} emails from ${data.total_labels} label(s).`);
                    closeEventSource();
                    break;

                case 'error':
                    updateProgressDisplay(data);
                    cancelProcessingBtn.style.display = 'none';
                    startProcessingBtn.disabled = false;
                    showProcessingStatus('error', 'Processing error', data.error_message || 'An error occurred during processing.');
                    showNotification('Email Processing Error', data.error_message || 'An error occurred during processing.');
                    closeEventSource();
                    break;

                case 'cancelled':
                    updateProgressDisplay(data);
                    cancelProcessingBtn.style.display = 'none';
                    startProcessingBtn.disabled = false;
                    showProcessingStatus('info', 'Processing cancelled', data.error_message || 'Processing was cancelled.');
                    showNotification('Email Processing Cancelled', 'Processing was cancelled by user.');
                    closeEventSource();
                    break;

                case 'heartbeat':
                    // Keep connection alive - no UI update needed
                    break;

                default:
                    console.log('Unknown event type:', type);
            }
        }

        // Check initial processing status
        async function checkInitialStatus() {
            if (!processingStatus) return;
            
            try {
                const response = await fetch('/emails/process/status');
                if (!response.ok) {
                    return;
                }
                const status = await response.json();
                
                if (status.in_progress) {
                    cancelProcessingBtn.style.display = 'inline-block';
                    startProcessingBtn.disabled = true;
                    // Connect to stream to get updates
                    connectToProgressStream();
                } else {
                    cancelProcessingBtn.style.display = 'none';
                    startProcessingBtn.disabled = false;
                }
            } catch (error) {
                console.error('Error checking initial status:', error);
            }
        }

        // Show processing status message
        function showProcessingStatus(type, message, details = '') {
            if (!processingStatus) return;
            
            // Remove all status classes
            processingStatus.classList.remove('success', 'error', 'info');
            // Add the new status class
            processingStatus.classList.add(type);
            processingStatus.style.display = 'block';
            processingStatusMessage.textContent = message;
            processingStatusDetails.textContent = details;
        }

        // Start processing
        if (startProcessingBtn) {
            startProcessingBtn.addEventListener('click', async () => {
                const allFolders = processAllFoldersCheckbox?.checked || false;
                const newOnly = newOnlyOption?.checked || false;
                let labels = null;
                
                if (!allFolders) {
                    const selectedOptions = Array.from(folderSelect?.selectedOptions || []);
                    labels = selectedOptions.map(opt => opt.value);
                    
                    if (labels.length === 0) {
                        showProcessingStatus('error', 'No folders selected', 'Please select at least one folder or check "Process All Folders".');
                        return;
                    }
                }
                
                const requestBody = {
                    all_folders: allFolders,
                    new_only: newOnly,
                    labels: labels
                };
                
                try {
                    startProcessingBtn.disabled = true;
                    showProcessingStatus('info', 'Starting processing...', 'Sending request to server...');
                    
                    const response = await fetch('/emails/process', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(requestBody)
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        showProcessingStatus('info', 'Processing started', result.message || 'Email processing has been initiated.');
                        cancelProcessingBtn.style.display = 'inline-block';
                        
                        // Connect to SSE stream for real-time updates
                        connectToProgressStream();
                    } else {
                        showProcessingStatus('error', 'Failed to start processing', result.detail || 'An error occurred while starting processing.');
                        startProcessingBtn.disabled = false;
                    }
                } catch (error) {
                    showProcessingStatus('error', 'Error starting processing', error.message);
                    startProcessingBtn.disabled = false;
                }
            });
        }

        // Cancel processing
        if (cancelProcessingBtn) {
            cancelProcessingBtn.addEventListener('click', async () => {
                try {
                    cancelProcessingBtn.disabled = true;
                    showProcessingStatus('info', 'Cancelling processing...', 'Sending cancellation request...');
                    
                    const response = await fetch('/emails/process/cancel', {
                        method: 'POST'
                    });
                    
                    const result = await response.json();
                    
                    if (result.cancelled) {
                        showProcessingStatus('info', 'Cancellation requested', result.message || 'Processing cancellation has been requested.');
                        // The SSE stream will send the cancelled event
                    } else {
                        showProcessingStatus('info', 'No processing in progress', result.message || 'No email processing is currently in progress.');
                        closeEventSource();
                    }
                } catch (error) {
                    showProcessingStatus('error', 'Error cancelling processing', error.message);
                } finally {
                    cancelProcessingBtn.disabled = false;
                }
            });
        }

        // Unified Import Controls (table layout, modal inputs, single status box)
        const importStatusText = document.getElementById('import-controls-status-text');
        const importCancelBtn = document.getElementById('import-controls-cancel-btn');
        const importInputModal = document.getElementById('import-input-modal');
        const importInputModalTitle = document.getElementById('import-input-modal-title');
        const importInputModalBody = document.getElementById('import-input-modal-body');
        const importInputModalCancel = document.getElementById('import-input-modal-cancel');
        const importInputModalSubmit = document.getElementById('import-input-modal-submit');

        let importInProgress = false;
        let currentImportType = null;
        let currentEventSource = null;
        const cancelEndpoints = {
            email_processing: '/emails/process/cancel',
            whatsapp: '/whatsapp/import/cancel',
            facebook: '/facebook/import/cancel',
            instagram: '/instagram/import/cancel',
            imessage: '/imessages/import/cancel',
            facebook_albums: '/facebook/albums/import/cancel',
            facebook_places: '/facebook/import-places/cancel',
            filesystem: '/images/import/cancel',
            thumbnails: '/images/process-thumbnails/cancel',
            contacts: '/contacts/extract/cancel'
        };

        function setImportStatus(text, isError = false) {
            if (importStatusText) {
                importStatusText.textContent = text || 'Idle';
                importStatusText.style.color = isError ? '#dc3545' : '#666';
            }
        }

        function setExecuting(importType, executing) {
            const btns = document.querySelectorAll('.import-execute-btn');
            btns.forEach(btn => {
                const type = btn.getAttribute('data-import');
                if (type === importType) {
                    btn.disabled = executing;
                    btn.innerHTML = executing ? '<i class="fas fa-spinner fa-spin"></i> Executing' : '<i class="fas fa-play"></i> Execute';
                    btn.style.backgroundColor = executing ? '#ffc107' : '';
                    btn.classList.toggle('import-executing', executing);
                } else {
                    btn.disabled = executing;
                    btn.classList.remove('import-executing');
                }
            });
            if (importCancelBtn) importCancelBtn.style.display = executing ? 'inline-block' : 'none';
        }

        function formatProgressLine(importType, data) {
            if (!data) return '';
            if (data.status_line) return data.status_line;
            if (data.error_message) return data.error_message;
            switch (importType) {
                case 'email_processing':
                    return `Label: ${data.current_label || '-'} | ${data.current_label_index || 0}/${data.total_labels || 0} | ${data.emails_processed || 0} emails processed`;
                case 'whatsapp':
                case 'facebook':
                case 'instagram':
                case 'imessage':
                    return `Conversation: ${data.current_conversation || '-'} | ${data.conversations_processed || 0}/${data.total_conversations || 0} | ${data.messages_imported || 0} msg (${data.messages_created || 0} new, ${data.messages_updated || 0} updated) | ${data.attachments_found || 0} attachments, ${data.attachments_missing || 0} missing | ${data.errors || 0} errors`;
                case 'facebook_albums':
                    return `Album: ${data.current_album || '-'} | ${data.albums_processed || 0}/${data.total_albums || 0} | ${data.images_imported || 0} imported, ${data.images_found || 0} found, ${data.images_missing || 0} missing | ${data.errors || 0} errors`;
                case 'facebook_places':
                    return data.status_line || `Places: ${data.places_imported || 0} imported`;
                case 'filesystem':
                    return `File: ${data.current_file || '-'} | ${data.files_processed || 0}/${data.total_files || 0} | ${data.images_imported || 0} imported, ${data.images_updated || 0} updated | ${data.errors || 0} errors`;
                case 'thumbnails':
                    const p1 = `Phase 1: ${data.phase1_scanned || 0} scanned, ${data.phase1_updated || 0} updated`;
                    const p2 = `Phase 2: ${data.phase2_scanned || 0}/${data.phase2_total || 0} scanned, ${data.phase2_processed || 0} processed, ${data.phase2_errors || 0} errors`;
                    return data.phase === '2' ? `${p1} | ${p2}` : p1;
                case 'contacts':
                    return data.status_line || 'Processing contacts...';
                default:
                    return JSON.stringify(data).substring(0, 100);
            }
        }

        function closeCurrentEventSource() {
            if (currentEventSource) {
                currentEventSource.close();
                currentEventSource = null;
            }
        }

        function finishImport(importType, success, message) {
            importInProgress = false;
            currentImportType = null;
            setExecuting(importType, false);
            closeCurrentEventSource();
            setImportStatus(message, !success);
            if (typeof loadImportControlLastRun === 'function') loadImportControlLastRun();
        }

        const importConfigs = {
            email_processing: { needsInput: true, title: 'Email Processing', run: async (vals) => { const body = { all_folders: vals.all_folders || false, labels: vals.all_folders ? null : (vals.labels || []), new_only: vals.new_only || false }; const r = await fetch('/emails/process', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); return r; }, stream: '/emails/process/stream' },
            whatsapp: { needsInput: true, title: 'WhatsApp Import', fields: [{ id: 'directory_path', key: 'whatsapp_import_directory', label: 'WhatsApp Export Directory', placeholder: 'e.g., C:\\iMazingBackup\\WhatsApp', required: true }], run: async (vals) => { const r = await fetch('/whatsapp/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ directory_path: vals.directory_path }) }); return r; }, stream: '/whatsapp/import/stream' },
            facebook: { needsInput: true, title: 'Facebook Messenger Import', fields: [{ id: 'directory_path', key: 'facebook_import_directory', label: 'Export Directory', placeholder: 'e.g., G:\\My Drive\\meta-2026-Jan-11\\your_facebook_activity\\messages\\e2ee_cutover', required: true }, { id: 'user_name', key: 'facebook_user_name', label: 'Your Name (Optional)', placeholder: 'e.g., Dave Burton', required: false }], run: async (vals) => { const r = await fetch('/facebook/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ directory_path: vals.directory_path, user_name: vals.user_name || null }) }); return r; }, stream: '/facebook/import/stream' },
            instagram: { needsInput: true, title: 'Instagram Import', fields: [{ id: 'directory_path', key: 'instagram_import_directory', label: 'Export Directory', placeholder: 'e.g., G:\\My Drive\\meta-2026-Jan-11\\your_instagram_activity\\messages\\inbox', required: true }, { id: 'user_name', key: 'instagram_user_name', label: 'Your Name (Optional)', placeholder: 'e.g., Dave Burton', required: false }], run: async (vals) => { const r = await fetch('/instagram/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ directory_path: vals.directory_path, user_name: vals.user_name || null }) }); return r; }, stream: '/instagram/import/stream' },
            imessage: { needsInput: true, title: 'iMessage Import', fields: [{ id: 'directory_path', key: 'imessage_directory_path', label: 'Directory Path', placeholder: 'Path to iMessage conversation subdirectories', required: true }], run: async (vals) => { const r = await fetch('/imessages/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ directory_path: vals.directory_path }) }); return r; }, stream: '/imessages/import/stream' },
            facebook_albums: { needsInput: true, title: 'Facebook Albums Import', fields: [{ id: 'directory_path', key: 'facebook_albums_import_directory', label: 'Export Directory', placeholder: 'e.g., G:\\My Drive\\meta-2026-Jan-11\\your_facebook_activity\\posts', required: true }], run: async (vals) => { const r = await fetch('/facebook/albums/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ directory_path: vals.directory_path }) }); return r; }, stream: '/facebook/albums/import/stream' },
            facebook_places: { needsInput: true, title: 'Facebook Places Import', fields: [{ id: 'file_path', key: 'facebook_places_import_file', label: 'Facebook Posts JSON File', placeholder: 'e.g., G:\\My Drive\\meta-2026-Jan-11\\your_posts__check_ins__photos_and_videos_1.json', required: true }], run: async (vals) => { const r = await fetch('/facebook/import-places', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ file_path: vals.file_path }) }); return r; }, stream: '/facebook/import-places/stream' },
            filesystem: { needsInput: true, title: 'Filesystem Image Import', fields: [{ id: 'root_directory', key: 'filesystem_import_directory', label: 'Root Directory(ies)', placeholder: 'e.g., C:\\Users\\Dave\\Pictures; D:\\Photos', required: true }, { id: 'max_images', key: 'filesystem_import_max_images', label: 'Max Images (Optional)', placeholder: 'Leave empty for all', required: false, type: 'number' }], run: async (vals) => { const body = { root_directory: vals.root_directory, create_thumb_and_get_exif: false }; if (vals.max_images) body.max_images = parseInt(vals.max_images, 10); const r = await fetch('/images/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); return r; }, stream: '/images/import/stream' },
            thumbnails: { needsInput: false, title: 'Image Processing', run: async () => { const r = await fetch('/images/process-thumbnails', { method: 'POST' }); return r; }, stream: '/images/process-thumbnails/stream' },
            contacts: { needsInput: false, title: 'Contacts Merge', run: async () => { const r = await fetch('/contacts/extract', { method: 'POST' }); return r; }, stream: '/contacts/extract/stream' }
        };

        async function showEmailProcessingModal(onSubmit) {
            importInputModalTitle.textContent = 'Email Processing';
            importInputModalBody.innerHTML = `
                <div class="setting-group" style="margin-bottom: 15px;">
                    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                        <input type="checkbox" id="import-modal-email-all-folders" style="cursor: pointer;">
                        <span>Process All Folders</span>
                    </label>
                </div>
                <div id="import-modal-email-folders-wrap" class="setting-group" style="margin-bottom: 15px;">
                    <label for="import-modal-email-folders" style="display: block; margin-bottom: 5px; font-weight: 500;">Select Folders</label>
                    <select id="import-modal-email-folders" multiple style="width: 100%; padding: 8px; border-radius: 4px; border: 1px solid #bfc9da; min-height: 120px;">
                        <option value="">Loading folders...</option>
                    </select>
                    <small style="color: #666; margin-top: 4px;">Hold Ctrl/Cmd to select multiple</small>
                </div>
                <div class="setting-group" style="margin-bottom: 15px;">
                    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                        <input type="checkbox" id="import-modal-email-new-only" style="cursor: pointer;">
                        <span>New Only (skip already imported emails)</span>
                    </label>
                </div>
            `;
            const allFoldersCb = document.getElementById('import-modal-email-all-folders');
            const foldersWrap = document.getElementById('import-modal-email-folders-wrap');
            const foldersSelect = document.getElementById('import-modal-email-folders');
            const newOnlyCb = document.getElementById('import-modal-email-new-only');

            const allFoldersVal = typeof getControlValue === 'function' ? getControlValue('process_all_folders', typeof controlDefaults !== 'undefined' ? controlDefaults.process_all_folders : false) : false;
            const newOnlyVal = typeof getControlValue === 'function' ? getControlValue('new_only_option', typeof controlDefaults !== 'undefined' ? controlDefaults.new_only_option : false) : false;
            allFoldersCb.checked = !!allFoldersVal;
            newOnlyCb.checked = !!newOnlyVal;
            foldersWrap.style.display = allFoldersCb.checked ? 'none' : 'block';

            allFoldersCb.addEventListener('change', () => { foldersWrap.style.display = allFoldersCb.checked ? 'none' : 'block'; });

            try {
                const response = await fetch('/emails/folders');
                if (!response.ok) throw new Error('Failed to load folders');
                const folders = await response.json();
                foldersSelect.innerHTML = '';
                folders.forEach(f => {
                    const opt = document.createElement('option');
                    opt.value = f.name;
                    opt.textContent = f.name;
                    foldersSelect.appendChild(opt);
                });
            } catch (e) {
                foldersSelect.innerHTML = '<option value="">Error loading folders</option>';
            }

            importInputModal.style.display = 'flex';
            importInputModal.style.alignItems = 'center';
            importInputModal.style.justifyContent = 'center';

            const doSubmit = () => {
                const all_folders = allFoldersCb.checked;
                const labels = all_folders ? [] : Array.from(foldersSelect.selectedOptions).map(o => o.value).filter(Boolean);
                const new_only = newOnlyCb.checked;
                if (!all_folders && labels.length === 0) return;
                if (typeof saveControlValue === 'function') {
                    saveControlValue('process_all_folders', all_folders);
                    saveControlValue('new_only_option', new_only);
                }
                importInputModal.style.display = 'none';
                onSubmit({ all_folders, labels, new_only });
            };

            importInputModalSubmit.onclick = doSubmit;
            importInputModalCancel.onclick = () => { importInputModal.style.display = 'none'; };
            importInputModal.onclick = (e) => { if (e.target === importInputModal) importInputModal.style.display = 'none'; };
        }

        function showImportModal(importType, onSubmit) {
            const cfg = importConfigs[importType];
            if (!cfg || !cfg.needsInput) { onSubmit({}); return; }
            importInputModalTitle.textContent = cfg.title;
            importInputModalBody.innerHTML = cfg.fields.map(f => `
                <div class="setting-group" style="margin-bottom: 15px;">
                    <label for="import-modal-${f.id}" style="display: block; margin-bottom: 5px; font-weight: 500;">${f.label}</label>
                    <input type="${f.type || 'text'}" id="import-modal-${f.id}" placeholder="${f.placeholder || ''}" style="width: 100%; padding: 8px; border-radius: 4px; border: 1px solid #bfc9da;">
                </div>
            `).join('');
            cfg.fields.forEach(f => {
                const el = document.getElementById(`import-modal-${f.id}`);
                if (el && typeof getControlValue === 'function') {
                    const val = getControlValue(f.key, typeof controlDefaults !== 'undefined' ? controlDefaults[f.key] : null);
                    el.value = (val !== undefined && val !== null ? String(val) : '') || '';
                }
            });
            importInputModal.style.display = 'flex';
            importInputModal.style.alignItems = 'center';
            importInputModal.style.justifyContent = 'center';

            const doSubmit = () => {
                const vals = {};
                let valid = true;
                cfg.fields.forEach(f => {
                    const el = document.getElementById(`import-modal-${f.id}`);
                    const v = el ? el.value.trim() : '';
                    if (f.required && !v) valid = false;
                    vals[f.id] = v;
                    if (typeof saveControlValue === 'function') saveControlValue(f.key, v);
                });
                if (!valid && cfg.fields.some(f => f.required)) return;
                importInputModal.style.display = 'none';
                onSubmit(vals);
            };

            importInputModalSubmit.onclick = doSubmit;
            importInputModalCancel.onclick = () => { importInputModal.style.display = 'none'; };
            importInputModal.onclick = (e) => { if (e.target === importInputModal) importInputModal.style.display = 'none'; };
            importInputModalBody.querySelectorAll('input').forEach(inp => {
                inp.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); doSubmit(); } });
            });
        }

        function connectToImportStream(importType) {
            closeCurrentEventSource();
            const cfg = importConfigs[importType];
            if (!cfg || !cfg.stream) return;
            currentEventSource = new EventSource(cfg.stream);
            currentEventSource.onmessage = (event) => {
                try {
                    const ed = JSON.parse(event.data);
                    const type = ed.type;
                    const data = ed.data || {};
                    if (type === 'progress' || type === 'status') {
                        const line = data.status_line || formatProgressLine(importType, data);
                        setImportStatus(line);
                    } else if (type === 'completed') {
                        const line = data.status_line || formatProgressLine(importType, data) || 'Completed successfully';
                        finishImport(importType, true, line);
                    } else if (type === 'error') {
                        finishImport(importType, false, data.error_message || data.status_line || 'Error');
                    } else if (type === 'cancelled') {
                        finishImport(importType, false, data.status_line || 'Cancelled');
                    }
                } catch (e) { console.warn('Import SSE parse error:', e); }
            };
            currentEventSource.onerror = () => {};
        }

        async function runImport(importType, values) {
            if (importInProgress) return;
            const cfg = importConfigs[importType];
            if (!cfg) return;
            importInProgress = true;
            currentImportType = importType;
            setExecuting(importType, true);
            setImportStatus('Starting...');

            try {
                const res = await cfg.run(values);
                const result = await res.json();
                if (!res.ok) {
                    finishImport(importType, false, result.detail || 'Failed to start');
                    return;
                }
                connectToImportStream(importType);
            } catch (e) {
                finishImport(importType, false, e.message || 'Error');
            }
        }

        document.querySelectorAll('.import-execute-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const importType = btn.getAttribute('data-import');
                if (importInProgress) return;
                if (importType === 'email_processing') {
                    showEmailProcessingModal((vals) => runImport(importType, vals));
                } else {
                    showImportModal(importType, (vals) => runImport(importType, vals));
                }
            });
        });

        if (importCancelBtn) {
            importCancelBtn.addEventListener('click', async () => {
                if (!currentImportType) return;
                const endpoint = cancelEndpoints[currentImportType];
                if (!endpoint) return;
                try {
                    await fetch(endpoint, { method: 'POST' });
                } catch (e) { console.warn('Cancel error:', e); }
            });
        }

        function resetImportControls() {
            closeCurrentEventSource();
            importInProgress = false;
            currentImportType = null;
            setImportStatus('Idle');
            if (importCancelBtn) importCancelBtn.style.display = 'none';
            document.querySelectorAll('.import-execute-btn').forEach(btn => {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-play"></i> Execute';
                btn.style.backgroundColor = '';
                btn.classList.remove('import-executing');
            });
            if (typeof loadImportControlLastRun === 'function') loadImportControlLastRun();
        }

        const importResetBtn = document.getElementById('import-controls-reset-btn');
        if (importResetBtn) {
            importResetBtn.addEventListener('click', () => resetImportControls());
        }

        async function checkInitialImportStatus() {
            const types = ['email_processing','imessage','whatsapp','facebook','instagram','facebook_albums','facebook_places','filesystem','thumbnails','contacts'];
            const statusEndpoints = { email_processing: '/emails/process/status', imessage: '/imessages/import/status', whatsapp: '/whatsapp/import/status', facebook: '/facebook/import/status', instagram: '/instagram/import/status', facebook_albums: '/facebook/albums/import/status', facebook_places: '/facebook/import-places/status', filesystem: '/images/import/status', thumbnails: '/images/process-thumbnails/status', contacts: '/contacts/extract/status' };
            for (const t of types) {
                try {
                    const r = await fetch(statusEndpoints[t]);
                    const s = await r.json();
                    if (s.in_progress) { importInProgress = true; currentImportType = t; setExecuting(t, true); if (importCancelBtn) importCancelBtn.style.display = 'inline-block'; connectToImportStream(t); return; }
                } catch (_) {}
            }
        }
        checkInitialImportStatus();


        
        // Sidebar button event listeners
        if (DOM.fbAlbumsSidebarBtn) {
            DOM.fbAlbumsSidebarBtn.addEventListener('click', () => {
                Modals.FBAlbums.open();
            });
        }

        // if (DOM.imageGallerySidebarBtn) {
        //     DOM.imageGallerySidebarBtn.addEventListener('click', () => {
        //         Modals.ImageGallery.open();
        //     });
        // }

        if (DOM.locationsSidebarBtn) {
            DOM.locationsSidebarBtn.addEventListener('click', () => {
                Modals.Locations.open();
            });
        }

        if (DOM.emailGallerySidebarBtn) {
            DOM.emailGallerySidebarBtn.addEventListener('click', () => {
                Modals.EmailGallery.open();
            });
        }

        if (DOM.newImageGallerySidebarBtn) {
            DOM.newImageGallerySidebarBtn.addEventListener('click', () => {
                Modals.NewImageGallery.open();
            });
        }

        const smsMessagesSidebarBtn = document.getElementById('sms-messages-sidebar-btn');
        if (smsMessagesSidebarBtn) {
            smsMessagesSidebarBtn.addEventListener('click', () => {
                Modals.SMSMessages.open();
            });
        }

        if (DOM.suggestionsSidebarBtn) {
            DOM.suggestionsSidebarBtn.addEventListener('click', () => {
                Modals.Suggestions.open();
            });
        }

        // if (DOM.haveYourSaySidebarBtn) {
        //     DOM.haveYourSaySidebarBtn.addEventListener('click', () => {
        //         Modals.HaveYourSay.open();
        //     });
        // }

        if (DOM.referenceDocumentsSidebarBtn) {
            DOM.referenceDocumentsSidebarBtn.addEventListener('click', () => {
                Modals.ReferenceDocuments.open();
            });
        }

        const contactsSidebarBtn = document.getElementById('contacts-sidebar-btn');
        if (contactsSidebarBtn) {
            contactsSidebarBtn.addEventListener('click', () => {
                Modals.Contacts.open();
            });
        }

        const relationshipsBtn = document.getElementById('relationships-btn');
        if (relationshipsBtn) {
            relationshipsBtn.addEventListener('click', () => {
                Modals.Relationships.open();
            });
        }

        if (DOM.artefactsSidebarBtn) {
            DOM.artefactsSidebarBtn.addEventListener('click', () => {
                Modals.Artefacts.open();
            });
        }

        if (DOM.sensitiveSidebarBtn) {
            DOM.sensitiveSidebarBtn.addEventListener('click', () => {
                Modals.SensitiveData.open();
            });
        }

        // Interviewee management event listeners
        if (DOM.intervieweeSelect) {
            DOM.intervieweeSelect.addEventListener('change', handleIntervieweeSelectChange);
        }

        if (DOM.addIntervieweeBtn) {
            DOM.addIntervieweeBtn.addEventListener('click', handleAddIntervieweeClick);
        }

        if (DOM.closeAddIntervieweeModal) {
            DOM.closeAddIntervieweeModal.addEventListener('click', handleAddIntervieweeCancel);
        }

        if (DOM.addIntervieweeSubmitBtn) {
            DOM.addIntervieweeSubmitBtn.addEventListener('click', handleAddIntervieweeSubmit);
        }

        if (DOM.addIntervieweeCancelBtn) {
            DOM.addIntervieweeCancelBtn.addEventListener('click', handleAddIntervieweeCancel);
        }

        // Add keyboard support for the modal
        if (DOM.newIntervieweeName) {
            DOM.newIntervieweeName.addEventListener('keydown', (event) => {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    handleAddIntervieweeSubmit();
                } else if (event.key === 'Escape') {
                    event.preventDefault();
                    handleAddIntervieweeCancel();
                }
            });
        }
    }

    function init() {
        // Info box modal: set up close first (before other inits that might throw)
        window.closeInfoBoxModal = function() {
            const modal = document.getElementById('info-box-modal');
            if (modal) {
                modal.classList.add('info-box-modal-closed');
                if (typeof UI !== 'undefined' && UI.setControlsEnabled) UI.setControlsEnabled(true);
            }
        };
        const infoBoxModal = document.getElementById('info-box-modal');
        if (infoBoxModal) {
            infoBoxModal.addEventListener('click', (e) => {
                if (e.target === infoBoxModal) window.closeInfoBoxModal();
            });
            document.getElementById('info-box-close-btn')?.addEventListener('click', window.closeInfoBoxModal);
            if (typeof UI !== 'undefined' && UI.setControlsEnabled) UI.setControlsEnabled(false);
        }

        Config.init(); // Loads and applies settings, sets up its listeners
        Chat.renderExistingMessages();
        VoiceSelector.init(); // Sets initial voice state, creativity lock, listeners
        Modals.initAll();
        //SSE.init();
        //InterviewerMode.init(); // Initialize interviewer mode
        initEventListeners(); // Attach main app event listeners
         window.onbeforeunload = () => { SSE.close(); };
    }
    return { init, processFormSubmit };
})();

App.init();
