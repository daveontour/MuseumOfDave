// --- START OF FILE script.js ---
document.addEventListener('DOMContentLoaded', () => {
    'use strict';

    // --- Polyfills or Global Helpers ---
    function generateUUID() { // Public Domain/MIT
        var d = new Date().getTime();
        var d2 = ((typeof performance !== 'undefined') && performance.now && (performance.now() * 1000)) || 0;
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16;
            if (d > 0) {
                r = (d + r) % 16 | 0;
                d = Math.floor(d / 16);
            } else {
                r = (d2 + r) % 16 | 0;
                d2 = Math.floor(d2 / 16);
            }
            return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
        });
    }

    // --- Constants ---
    const CONSTANTS = {
        VOICE_IMAGES: {
            'expert': 'expert.png', 'male_friend': 'male-friend.png', 'female_friend': 'female-friend.png',
            'psychologist': 'psychologist.png', 'after_death': 'after-death.png', 'secret_admirer': 'secret-admirer.png',
            'bar_girl': 'bar-girl.png', 'parents': 'parents.png', 'preacher': 'preacher.png',
            'dave': 'dave.png', 'irish': 'irish.png', 'haiku': 'haiku.png',
            'insult': 'insult.png', 'earthchild': 'earthchild.png',
            'expert_sm': 'expert_sm.png', 'male_friend_sm': 'male-friend_sm.png', 'female_friend_sm': 'female-friend_sm.png',
            'psychologist_sm': 'psychologist_sm.png', 'after_death_sm': 'after-death_sm.png', 'secret_admirer_sm': 'secret-admirer_sm.png',
            'bar_girl_sm': 'bar-girl_sm.png', 'parents_sm': 'parents_sm.png', 'preacher_sm': 'preacher_sm.png',
            'dave_sm': 'dave_sm.png', 'irish_sm': 'irish_sm.png', 'haiku_sm': 'haiku_sm.png',
            'insult_sm': 'insult_sm.png', 'earthchild_sm': 'earthchild_sm.png',
        },
        FUNCTION_NAMES: Object.freeze({
            FirstFunction: "testFunction",
            SecondFunction: "showFBMessengerOptions",
            ThirdFunction: "showFBAlbumsOptions",
            FourthFunction: "openGeoModal",
            FifthFunction: "showLocationInfo",
            SixthFunction: "showImageGallery",
            SeventhFunction: "testEmail",
            EighthFunction: "showEmailGallery"
        }),
        VOICE_DESCRIPTIONS: {
            'expert': 'a knowledgeable expert who provides accurate, factual information',
            'psychologist': 'a compassionate therapist offering psychological insights',
            'after_death': 'an uptight British professor',
            'secret_admirer': 'a romantic soul expressing deep affection who is very shy and reserved and remained annonymous',
            'bar_girl': 'a friendly Thai bar girl called Lucky offering conversation and advice',
            'parents': 'caring parental figures providing guidance and support',
            'preacher': 'a spiritual advisor who is extremely pious and judgemental',
            'dave': 'Dave in his own voice',
            'irish': 'a cheerful Irish comedian who is very funny and has a great sense of humour and responds in limmericks',
            'haiku': 'a poetic soul who responds in haiku form',
            'insult': 'a comedic roaster delivering playful burns',
            'earthchild': 'a free spirit sharing natural wisdom',
            'female_friend': 'a supportive female friend offering caring advice',
            'male_friend': 'a supportive male friend offering caring advice'
        },
        API_PATHS: {
            CHAT: '/chat',
            NEW_CHAT: '/new',
            INTERVIEW: '/interviewer/interview',
            NEW_INTERVIEW: '/interviewer/newinterview',
            CHECK_INTERVIEW_DATA: '/interviewer/checkinterviewdata',
            RESUME_INTERVIEW: '/interviewer/resumeinterview',
            PAUSE_INTERVIEW: '/interviewer/pauseinterview',
            FINISH_INTERVIEW: '/interviewer/finishinterview',
            WRITE_INTERIM_BIO: '/interviewer/writeinterimbio',
            WRITE_FINAL_BIO: '/interviewer/writefinalbio',
            VOICE: '/voice',
            SUGGESTIONS_JSON: '/static/Suggestions.json',
            FB_CHATTERS: '/facebook-chatters/one_to_one',
            CONTACTS: '/getContacts',
            MESSAGES_BY_CONTACT: '/getMessagesByContact',
            MESSAGES_BY_CONTACT_V2: '/getConversationsByParticipant?name=',
            ALBUMS: '/getAlbums',
            EVENTS: '/events',
            HAVE_YOUR_SAY: '/HaveYourSay',
            WHAT_ARE_PEOPLE_SAYING: '/WhatArePeopleSaying'
        },
        LOCAL_STORAGE_KEYS: {
            CHAT_SETTINGS: 'chatSettings'
        }
    };

    // --- DOM Element Cache ---
    const DOM = {
        chatBox: document.getElementById('chat-box'),
        chatForm: document.getElementById('chat-form'),
        userInput: document.getElementById('user-input'),
        sendButton: document.getElementById('send-button'),
        suggestionsBtn: document.getElementById('suggestions-btn'),
        newChatButton: document.getElementById('new-chat-btn'),
        loadingIndicator: document.getElementById('loading-indicator'),
        errorDisplay: document.getElementById('error-display'),
        infoBox: document.getElementById('info-box'),
        hamburgerMenu: document.getElementById('hamburger-menu'),
        configPage: document.querySelector('.config-page'),
        closeConfigBtn: document.getElementById('close-config'),
        chatMain: document.querySelector('.chat-main'),
        messageFontSize: document.getElementById('message-font-size'),
        creativityLevel: document.getElementById('creativity-level'),
        showAudioTags: document.getElementById('show-audio-tags'),
        showImageTags: document.getElementById('show-image-tags'),
        showJsonTags: document.getElementById('show-json-tags'),
        autoVoiceShortResponses: document.getElementById('auto-voice-short-responses'),
        companionModeCheckbox: document.getElementById('companion-mode'),
        voiceRadios: document.querySelectorAll('input[name="voice"]'),
        moodSelector: document.getElementById('mood-selector'),
        daveMood: document.getElementById('dave-mood'),
        voicePreviewImg: document.querySelector('.preview-image'),
        voicePreviewDesc: document.querySelector('.preview-description'),
        loadingVoiceImage: document.querySelector('#loading-indicator .loading-voice-image'),
        voiceIcons: document.querySelectorAll('.voice-icon'),
        voiceIconWrappers: document.querySelectorAll('.voice-icon-wrapper'),
        // New voice select dropdown
        voiceSelect: document.getElementById('voice-select'),
        selectedVoiceImage: document.getElementById('selected-voice-image'),
        // Modals & Modal Elements
        suggestionsModal: document.getElementById('tile-suggestions-modal'),
        closeSuggestionsModalBtn: document.getElementById('modal-suggestions-close-btn'),
        suggestionsListContainer: document.getElementById('tile-suggestions-container'),
        fbAlbumsModal: document.getElementById('fb-albums-modal'),
        fbAlbumsSelect: document.getElementById('fb-albums-select'),
        closeFBAlbumsModalBtn: document.getElementById('close-fb-albums-modal'),
        fbAlbumsCancelBtn: document.getElementById('fb-albums-cancel-btn'),
        fbAlbumsOkBtn: document.getElementById('fb-albums-ok-btn'),
        fbImageModal: document.getElementById('fb-album-modal'),
        fbImageModalTitle: document.getElementById('fb-album-modal-title'),
        fbImageModalDescription: document.getElementById('fb-album-modal-description'),
        fbImageContainer: document.getElementById('fb-album-container'),
        fbImageModalCloseBtn: document.getElementById('close-fb-album-modal'),
        haveYourSayBtn: document.getElementById('have-your-say-btn'),
        haveYourSayModal: document.getElementById('have-your-say-modal'),
        closeHaveYourSayModalBtn: document.getElementById('close-have-your-say-modal'),
        startDictationBtn: document.getElementById('start-dictation-btn'),
        stopDictationBtn: document.getElementById('stop-dictation-btn'),
        submitHaveYourSayBtn: document.getElementById('submit-have-your-say-btn'),
        cancelHaveYourSayBtn: document.getElementById('cancel-have-your-say-btn'),
        haveYourSayTextarea: document.getElementById('have-your-say-textarea'),
        dictationStatus: document.getElementById('dictation-status'),
        haveYourSayName: document.getElementById('have-your-say-name'),
        haveYourSayRelationship: document.getElementById('have-your-say-relationship'),
        // Chat dictation elements
        chatStartDictationBtn: document.getElementById('chat-start-dictation-btn'),
        chatStopDictationBtn: document.getElementById('chat-stop-dictation-btn'),
        chatDictationStatus: document.getElementById('chat-dictation-status'),
        geoMetadataModal: document.getElementById('geo-metadata-modal'),
        geoList: document.getElementById('geo-metadata-list'),
        geoImage: document.getElementById('geo-metadata-image'),
        geoMapFixedBtn: document.getElementById('geo-map-fixed-btn'),
        closeGeoMetadataModalBtn: document.getElementById('close-geo-metadata-modal'),
        shufflePhotosBtn: document.getElementById('shuffle-photos-btn'),
        leafletmap: document.getElementById('map'),
        tabButtons: document.querySelectorAll('.geo-tab-btn'),
        tabContents: document.querySelectorAll('.geo-metadata-tab-content'),
        geoMetaDataIframe: document.getElementById('geo-metadata-image'),
        geoMetaDataInstructions: document.getElementById('geo-metadata-instructions'),

        // Confirmation Modal
        confirmationModal: document.getElementById('confirmation-modal'),
        confirmationModalTitle: document.getElementById('confirmation-modal-title'),
        confirmationModalText: document.getElementById('confirmation-modal-text'),
        confirmationModalConfirmBtn: document.getElementById('confirmation-modal-confirm'),
        confirmationModalCancelBtn: document.getElementById('confirmation-modal-cancel'),
        confirmationModalCloseBtn: document.getElementById('close-confirmation-modal'),
        yearFilter: document.getElementById('year-filter'),
        monthFilter: document.getElementById('month-filter'),
        imageDetails: document.getElementById('image-details'),
        imageGalleryModalContent: document.getElementById('image-gallery-modal-content'),
        imageGalleryModal: document.getElementById('image-gallery-modal'),
        closeImageGalleryModalBtn: document.getElementById('close-image-gallery-modal'),
        imageGalleryModalTitle: document.getElementById('image-gallery-modal-title'),
        imageGalleryList: document.getElementById('image-gallery-list'),
        imageGalleryImage: document.getElementById('image-gallery-image'),
        imageGalleryMap: document.getElementById('image-gallery-map'),
        imageGalleryInstructions: document.getElementById('image-gallery-instructions'),
        imageGalleryFixedBtn: document.getElementById('image-gallery-fixed-btn'),
        imageGalleryYearFilter: document.getElementById('image-gallery-year-filter'),
        imageGalleryMonthFilter: document.getElementById('image-gallery-month-filter'),
        imageGallerySourceFilter: document.getElementById('image-gallery-source-filter'),
        imageGalleryLocationFilter: document.getElementById('image-gallery-location-filter'),
        imageGallerySearch: document.getElementById('image-gallery-search'),
        imageGalleryImageDetails: document.getElementById('image-gallery-image-details'),
        imageGalleryAudioContainer: document.getElementById('image-gallery-audio-container'),
        imageGalleryAudioPlayer: document.getElementById('image-gallery-audio-player'),
        imageGalleryVideoContainer: document.getElementById('image-gallery-video-container'),
        imageGalleryVideoPlayer: document.getElementById('image-gallery-video-player'),
        imageGalleryPdfContainer: document.getElementById('image-gallery-pdf-container'),
        imageGalleryPdfViewer: document.getElementById('image-gallery-pdf-viewer'),
        imageGallerySearchBtn: document.getElementById('image-gallery-search-btn'),
        imageGalleryClearBtn: document.getElementById('image-gallery-clear-btn'),
        // Change User ID Modal elements
        changeUserIdBtn: document.getElementById('change-user-id-btn'),
        changeUserIdModal: document.getElementById('change-user-id-modal'),
        closeChangeUserIdModalBtn: document.getElementById('close-change-user-id-modal'),
        changeUserIdCancelBtn: document.getElementById('change-user-id-cancel-btn'),
        changeUserIdConfirmBtn: document.getElementById('change-user-id-confirm-btn'),
        currentUserIdInput: document.getElementById('current-user-id'),
        newUserIdInput: document.getElementById('new-user-id'),
        downloadImageGalleryBtn: document.getElementById('download-image-gallery-btn'),
        // Email Gallery Modal Elements
        emailGalleryModal: document.getElementById('email-gallery-modal'),
        closeEmailGalleryModalBtn: document.getElementById('close-email-gallery-modal'),
        emailGalleryList: document.getElementById('email-gallery-list'),
        emailGalleryContent: document.querySelector('.email-gallery-content'),
        emailGalleryInstructions: document.getElementById('email-gallery-instructions'),
        emailGalleryEmailContent: document.getElementById('email-gallery-email-content'),
        emailGallerySearch: document.getElementById('email-gallery-search'),
        emailGallerySender: document.getElementById('email-gallery-sender'),
        emailGalleryRecipient: document.getElementById('email-gallery-recipient'),
        emailGalleryToFrom: document.getElementById('email-gallery-to-from'),
        emailGalleryYearFilter: document.getElementById('email-gallery-year-filter'),
        emailGalleryMonthFilter: document.getElementById('email-gallery-month-filter'),
        emailGalleryBusinessFilter: document.getElementById('email-gallery-business-filter'),
        emailGalleryAttachmentsFilter: document.getElementById('email-gallery-attachments-filter'),
        emailGalleryFolderFilter: document.getElementById('email-gallery-folder-filter'),
        emailGallerySearchBtn: document.getElementById('email-gallery-search-btn'),
        emailGalleryClearBtn: document.getElementById('email-gallery-clear-btn'),
        emailGalleryEmailDetails: document.getElementById('email-gallery-email-details'),
        // Email Gallery Button
        emailGalleryBtn: document.getElementById('email-gallery-btn'),
        // Dropup Elements
        dropupBtn: document.getElementById('dropup-btn'),
        dropupContainer: document.querySelector('.dropup'),
        fbAlbumsDropupBtn: document.getElementById('fb-albums-dropup-btn'),
        imageGalleryDropupBtn: document.getElementById('image-gallery-dropup-btn'),
        locationsDropupBtn: document.getElementById('locations-dropup-btn'),
        emailGalleryDropupBtn: document.getElementById('email-gallery-dropup-btn'),
        suggestionsDropupBtn: document.getElementById('suggestions-dropup-btn'),
        haveYourSayDropupBtn: document.getElementById('have-your-say-dropup-btn'),
        // New sidebar buttons
        fbAlbumsSidebarBtn: document.getElementById('fb-albums-sidebar-btn'),
        imageGallerySidebarBtn: document.getElementById('image-gallery-sidebar-btn'),
        locationsSidebarBtn: document.getElementById('locations-sidebar-btn'),
        emailGallerySidebarBtn: document.getElementById('email-gallery-sidebar-btn'),
        suggestionsSidebarBtn: document.getElementById('suggestions-sidebar-btn'),
        haveYourSaySidebarBtn: document.getElementById('have-your-say-sidebar-btn'),
        // Interviewer mode elements
        interviewerModeBtn: document.getElementById('interviewer-mode-btn'),
        interviewerMain: document.querySelector('.interviewer-main'),
        interviewerChatBox: document.getElementById('interviewer-chat-box'),
        interviewerChatForm: document.getElementById('interviewer-chat-form'),
        interviewerUserInput: document.getElementById('interviewer-user-input'),
        interviewerSendButton: document.getElementById('interviewer-send-button'),
        interviewerLoadingIndicator: document.getElementById('interviewer-loading-indicator'),
        interviewerErrorDisplay: document.getElementById('interviewer-error-display'),
        interviewerStartDictationBtn: document.getElementById('interviewer-start-dictation-btn'),
        interviewerStopDictationBtn: document.getElementById('interviewer-stop-dictation-btn'),
        interviewerDictationStatus: document.getElementById('interviewer-dictation-status'),
        exitInterviewerModeBtn: document.getElementById('exit-interviewer-mode-btn'),
        // Interview control buttons
        startInterviewBtn: document.getElementById('start-interview-btn'),
        resumeInterviewBtn: document.getElementById('resume-interview-btn'),
        pauseInterviewBtn: document.getElementById('pause-interview-btn'),
        writeInterimBioBtn: document.getElementById('write-interim-bio-btn'),
        finishInterviewBtn: document.getElementById('finish-interview-btn'),
        writeFinalBioBtn: document.getElementById('write-final-bio-btn'),
        resetInterviewBtn: document.getElementById('reset-interview-btn'),
        intervieweeSelect: document.getElementById('interviewee-select'),
        addIntervieweeBtn: document.getElementById('add-interviewee-btn'),
        addIntervieweeModal: document.getElementById('add-interviewee-modal'),
        closeAddIntervieweeModal: document.getElementById('close-add-interviewee-modal'),
        newIntervieweeName: document.getElementById('new-interviewee-name'),
        addIntervieweeSubmitBtn: document.getElementById('add-interviewee-submit-btn'),
        addIntervieweeCancelBtn: document.getElementById('add-interviewee-cancel-btn'),
        interviewPurposeSelect: document.getElementById('interview-purpose'),
        // Single Image Modal Elements
        singleImageModal: document.getElementById('single-image-modal'),
        singleImageModalImg: document.getElementById('single-image-modal-img'),
        singleImageModalAudio: document.getElementById('single-image-modal-audio'),
        singleImageModalVideo: document.getElementById('single-image-modal-video'),
        singleImageModalPdf: document.getElementById('single-image-modal-pdf'),
        singleImageDetails: document.getElementById('single-image-details'),
        closeSingleImageModalBtn: document.getElementById('close-single-image-modal'),
        downloadSingleImageBtn: document.getElementById('download-single-image-btn'),
    };

    // Debug DOM elements
    console.log('DOM elements found:');
    console.log('interviewerModeBtn:', DOM.interviewerModeBtn);
    console.log('interviewerMain:', DOM.interviewerMain);
    console.log('voicePreviewImg:', DOM.voicePreviewImg);
    console.log('voicePreviewDesc:', DOM.voicePreviewDesc);

    // --- Configure Marked ---
    marked.setOptions({
        highlight: function(code, lang) {
            const language = hljs.getLanguage(lang) ? lang : 'plaintext';
            return hljs.highlight(code, { language }).value;
        },
        langPrefix: 'hljs language-', breaks: true, gfm: true
    });

    // --- State ---
    const AppState = {
        clientId: generateUUID(),
        sseEventSource: null,
        dictationRecognition: null,
        isDictationListening: false,
        finalDictationTranscript: '',
        // Chat dictation state
        chatDictationRecognition: null,
        isChatDictationListening: false,
        finalChatDictationTranscript: '',
        // Interviewer mode state
        isInterviewerMode: false,
        interviewerDictationRecognition: null,
        isInterviewerDictationListening: false,
        finalInterviewerDictationTranscript: '',
        // Interview state management
        interviewState: 'initial', // 'initial', 'active', 'paused', 'finished'
        interviewSubjectName: 'Dave' // Name of the person being interviewed
    };

    let mapViewInitialized = false;
 // Track the current marker on the main map

    // --- UI Helper Module ---
    const UI = (() => {
        function clearError() {
            DOM.errorDisplay.textContent = '';
            DOM.errorDisplay.style.display = 'none';
        }

        function displayError(message) {
            console.error("Error displayed:", message);
            DOM.errorDisplay.textContent = `Error: ${message}`;
            DOM.errorDisplay.style.display = 'block';
            DOM.loadingIndicator.style.display = 'none'; // Hide loading indicator on error
        }

        function scrollToBottom() {
            setTimeout(() => { DOM.chatBox.scrollTop = DOM.chatBox.scrollHeight; }, 50);
        }

        function setControlsEnabled(enabled) {
            DOM.userInput.disabled = !enabled;
            DOM.sendButton.disabled = !enabled;
            // DOM.suggestionsBtn.disabled = !enabled;
        }

        function showLoadingIndicator() {
            VoiceSelector.updateLoadingIndicatorImage(); // Update image first
            DOM.loadingIndicator.style.display = 'flex';
        }

        function hideLoadingIndicator() {
            DOM.loadingIndicator.style.display = 'none';
        }
        
        function getWorkModePrefix() {
            // Since workModeCheckbox was replaced with interviewer mode button,
            // we'll use the interviewer mode state instead
           // return AppState.isInterviewerMode ? "Do not respond with any sexual related material. " : "";
           return ""
        }

        return {
            clearError, displayError, scrollToBottom, setControlsEnabled,
            showLoadingIndicator, hideLoadingIndicator, getWorkModePrefix
        };
    })();

    // --- Configuration Module ---
    const Config = (() => {
        function applySettings() {
            document.documentElement.style.setProperty('--message-font-size', `${DOM.messageFontSize.value}px`);
            DOM.messageFontSize.nextElementSibling.textContent = `${DOM.messageFontSize.value}px`;
            // Apply audio tag visibility directly (CSS might be better for this)
            document.body.classList.toggle('hide-audio-tags', !DOM.showAudioTags.checked);

            // Apply creativity level text
            if (DOM.creativityLevel.nextElementSibling) {
                 DOM.creativityLevel.nextElementSibling.textContent = DOM.creativityLevel.value;
            }
        }

        function loadSettings() {
            const settings = JSON.parse(localStorage.getItem(CONSTANTS.LOCAL_STORAGE_KEYS.CHAT_SETTINGS) || '{}');
            if (settings.messageFontSize && DOM.messageFontSize) DOM.messageFontSize.value = settings.messageFontSize;
            if (settings.creativityLevel && DOM.creativityLevel) DOM.creativityLevel.value = settings.creativityLevel;
            if (settings.showAudioTags !== undefined && DOM.showAudioTags) DOM.showAudioTags.checked = settings.showAudioTags;
            if (settings.showImageTags !== undefined && DOM.showImageTags) DOM.showImageTags.checked = settings.showImageTags;
            if (settings.showJsonTags !== undefined && DOM.showJsonTags) DOM.showJsonTags.checked = settings.showJsonTags;
            if (settings.autoVoiceShortResponses !== undefined && DOM.autoVoiceShortResponses) DOM.autoVoiceShortResponses.checked = settings.autoVoiceShortResponses;

            
            applySettings();
        }

        function saveSettings() {
            const settings = {
                messageFontSize: DOM.messageFontSize ? DOM.messageFontSize.value : '',
                creativityLevel: DOM.creativityLevel ? DOM.creativityLevel.value : '',
                showAudioTags: DOM.showAudioTags ? DOM.showAudioTags.checked : false,
                showImageTags: DOM.showImageTags ? DOM.showImageTags.checked : false,
                showJsonTags: DOM.showJsonTags ? DOM.showJsonTags.checked : false,
                autoVoiceShortResponses: DOM.autoVoiceShortResponses ? DOM.autoVoiceShortResponses.checked : false,

            };
            localStorage.setItem(CONSTANTS.LOCAL_STORAGE_KEYS.CHAT_SETTINGS, JSON.stringify(settings));
            applySettings();
        }

        function init() {
            loadSettings();
            [DOM.messageFontSize, DOM.creativityLevel, DOM.showAudioTags, DOM.showImageTags, DOM.showJsonTags, DOM.companionModeCheckbox, DOM.autoVoiceShortResponses].forEach(el => {
                if (el && el.type === 'checkbox') {
                    el.addEventListener('change', saveSettings);
                } else if (el) {
                    el.addEventListener('input', saveSettings);
                }
            });
            // Special handling for creativityLevel label update on input
            if (DOM.creativityLevel) {
                DOM.creativityLevel.addEventListener('input', (e) => {
                    if (e.target.nextElementSibling) {
                        e.target.nextElementSibling.textContent = e.target.value;
                    }
                });
            }
        }
        return { init, saveSettings, loadSettings }; // Expose saveSettings for voice selector
    })();

    // --- Chat Module ---
    const Chat = (() => {
        function renderMarkdown(element, text) {
            const sanitizedText = text.replace(/</g, "<").replace(/>/g, ">"); // Basic sanitization
            element.innerHTML = marked.parse(sanitizedText || '');
        }

        function _createMessageElement(role, messageId) {
            const messageElement = document.createElement('div');
            messageElement.classList.add('message', role === 'suggestion' ? 'user-message' : `${role}-message`);
            if (role === 'suggestion') messageElement.style.backgroundColor = "#f4f778";
            if (messageId) messageElement.id = messageId;
            return messageElement;
        }


        function _addVoiceBranding(messageElement, role) {
            if (role === 'assistant') {
                const selectedVoice = VoiceSelector.getSelectedVoice();
                messageElement.classList.add(`voice-${selectedVoice}`);
                const voiceImageSmall = document.createElement('img');
                voiceImageSmall.className = 'message-voice-image';
                voiceImageSmall.src = `/static/images/${CONSTANTS.VOICE_IMAGES[selectedVoice + '_sm']}`;
                voiceImageSmall.alt = `${selectedVoice} character`;
                messageElement.appendChild(voiceImageSmall);
            }
        }

        function _addCopyButton(messageElement, role, text, contentElement) {
            const copyButton = document.createElement('button');
            copyButton.className = 'copy-hover-btn';
            copyButton.innerHTML = '<i class="fa-regular fa-copy"></i> Copy';
            copyButton.addEventListener('click', async () => {
                try {
                    let textToCopy = text;
                    if (['assistant', 'model', 'system'].includes(role)) {
                        const rawMarkdown = contentElement.querySelector('.raw-markdown');
                        textToCopy = rawMarkdown ? rawMarkdown.value : text;
                    }
                    await navigator.clipboard.writeText(textToCopy);
                    copyButton.innerHTML = '<i class="fa-solid fa-check"></i> Copied!';
                    copyButton.classList.add('copied');
                    setTimeout(() => {
                        copyButton.innerHTML = '<i class="fa-regular fa-copy"></i> Copy';
                        copyButton.classList.remove('copied');
                    }, 2000);
                } catch (err) {
                    console.error('Failed to copy text:', err);
                    copyButton.innerHTML = '<i class="fa-solid fa-xmark"></i> Failed';
                    copyButton.classList.add('error');
                     setTimeout(() => {
                        copyButton.innerHTML = '<i class="fa-regular fa-copy"></i> Copy';
                        copyButton.classList.remove('error');
                    }, 2000);
                }
            });
            messageElement.appendChild(copyButton);
        }

        function _renderMessageContent(contentElement, text, role, isMarkdown) {
            contentElement.dataset.role = (role === 'suggestion') ? "user" : role;
            if (role === 'suggestion') contentElement.style.backgroundColor = "#f4f778";

            if ((isMarkdown && role !== 'user') || role === 'suggestion') {
                const rawMarkdown = document.createElement('textarea');
                rawMarkdown.className = 'raw-markdown';
                rawMarkdown.style.display = 'none';
                rawMarkdown.value = text;
                contentElement.appendChild(rawMarkdown);
                renderMarkdown(contentElement, text);
            } else {
                contentElement.textContent = text;
            }
        }

        function _addImagePreviews(messageElement, embeddedJson) {
           
            if (embeddedJson && embeddedJson.attachments && Array.isArray(embeddedJson.attachments) && DOM.showImageTags.checked) {
                const imageButtonsContainer = document.createElement('div');
                imageButtonsContainer.className = 'image-buttons-container';
                embeddedJson.attachments.forEach(uri => {
                    const imagePreview = document.createElement('img');
                    imagePreview.src = uri+'&preview=true&resize_to=100';
                    imagePreview.alt = 'Image Preview';
                    imagePreview.className = 'image-preview';
                    imagePreview.style.cursor = 'pointer';
                    imagePreview.loading = 'lazy';
                    imagePreview.onclick = () => _imageSwitcher(embeddedJson.attachments, uri); // Delegate to modal
                    imageButtonsContainer.appendChild(imagePreview);
                });
                messageElement.appendChild(imageButtonsContainer);
            }
        }

        function _imageSwitcher(images, uri){

            if (images.length > 1) {
                Modals.MultiImageDisplay.showMultiImageModal(images, uri);
            } else {
                Modals.SingleImageDisplay.showSingleImageModal(images[0], uri, 0, 0, 0);
            }
                
        }

        function _addJsonViewer(messageElement, embeddedJson) {
            if (embeddedJson && DOM.showJsonTags.checked) {
                const jsonWrapper = document.createElement('div');
                jsonWrapper.className = 'json-wrapper';
                const jsonToggle = document.createElement('button');
                jsonToggle.className = 'json-toggle';
                jsonToggle.innerHTML = '<i class="fa-solid fa-chevron-down"></i>';
                const jsonContent = document.createElement('div');
                jsonContent.className = 'json-content';
                jsonContent.style.display = 'none';
                const pre = document.createElement('pre');
                pre.textContent = JSON.stringify(embeddedJson, null, 2);
                jsonContent.appendChild(pre);
                jsonToggle.onclick = () => {
                    const isHidden = jsonContent.style.display === 'none';
                    jsonContent.style.display = isHidden ? 'block' : 'none';
                    jsonToggle.innerHTML = isHidden ? '<i class="fa-solid fa-chevron-up"></i>' : '<i class="fa-solid fa-chevron-down"></i>';
                };
                jsonWrapper.appendChild(jsonToggle);
                jsonWrapper.appendChild(jsonContent);
                messageElement.appendChild(jsonWrapper);
            }
        }

        function _addSpeakButton(contentElement, role) {
            if (['assistant', 'model'].includes(role) && DOM.showAudioTags.checked) {
                const speakButton = document.createElement('button');
                speakButton.className = 'speak-button';
                speakButton.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M14,3.23V5.29C16.89,6.15 19,8.83 19,12C19,15.17 16.89,17.84 14,18.7V20.77C18,19.86 21,16.28 21,12C21,7.72 18,4.14 14,3.23M16.5,12C16.5,10.23 15.5,8.71 14,7.97V16C15.5,15.29 16.5,13.76 16.5,12M3,9V15H7L12,20V4L7,9H3Z"/></svg>';
                
                const audioElement = document.createElement('audio');
                audioElement.controls = true;
                audioElement.style.display = 'none';

                const statusMessage = document.createElement('div');
                statusMessage.className = 'audio-status';
                statusMessage.style.display = 'none'; // CSS handles this
                
                contentElement.appendChild(speakButton);
                contentElement.appendChild(audioElement);
                contentElement.appendChild(statusMessage);

                const showAudioStatus = (message, isError = false) => {
                    statusMessage.textContent = message;
                    statusMessage.style.display = 'block';
                    statusMessage.style.color = isError ? '#dc3545' : '#666';
                };

                audioElement.addEventListener('playing', () => { statusMessage.style.display = 'none'; });
                audioElement.addEventListener('error', () => { showAudioStatus('Error loading audio', true); });

                speakButton.onclick = async () => {
                    try {
                        showAudioStatus('Loading audio...');
                        const selectedVoice = VoiceSelector.getSelectedVoice();
                        const audioBlob = await ApiService.fetchVoice({ text: contentElement.textContent, voice: selectedVoice });
                        if (!audioBlob) throw new Error("Voice conversion failed or returned no data.");

                        audioElement.src = URL.createObjectURL(audioBlob);
                        audioElement.style.display = 'block';
                        speakButton.style.display = 'none';
                        statusMessage.style.display = 'none';
                        audioElement.play();
                    } catch (error) {
                        console.error('Error playing voice:', error);
                        showAudioStatus(error.message || 'Error loading audio', true);
                    }
                };
            }
        }

        function addMessage(role, text, isMarkdown = true, messageId = null, embeddedJson = null) {
            const messageElement = _createMessageElement(role, messageId);
            _addVoiceBranding(messageElement, role);

            const contentElement = document.createElement('div');
            contentElement.classList.add('message-content');
            _renderMessageContent(contentElement, text, role, isMarkdown);
            _addCopyButton(messageElement, role, text, contentElement); // Pass contentElement for raw markdown access

            messageElement.appendChild(contentElement);

            _addImagePreviews(messageElement, embeddedJson);
            _addJsonViewer(messageElement, embeddedJson);
            _addSpeakButton(contentElement, role); // Pass contentElement as it appends to it

            DOM.chatBox.appendChild(messageElement);
            UI.scrollToBottom();
            
            // Auto-voice for short responses
            if (role === 'assistant' && DOM.autoVoiceShortResponses && DOM.autoVoiceShortResponses.checked) {
                const wordCount = text.trim().split(/\s+/).length;
                if (wordCount < 60) {
                    // Automatically trigger voice API for short responses
                    setTimeout(() => {
                        const speakButton = messageElement.querySelector('.speak-button');
                        if (speakButton) {
                            speakButton.click();
                        }
                    }, 500); // Small delay to ensure the message is fully rendered
                }
            }
            
            return messageElement;
        }

        function addEmail(email, messageId = null, embeddedJson = null) {
            const messageElement = _createMessageElement('email', messageId);
            
            const contentElement = document.createElement('div');
            contentElement.classList.add('message-content', 'email-content');
            
            // Create email header
            const emailHeader = document.createElement('div');
            emailHeader.classList.add('email-header');
            
            // From field
            if (email.from) {
                const fromField = document.createElement('div');
                fromField.classList.add('email-field');
                fromField.innerHTML = `<strong>From:</strong> ${email.from}`;
                emailHeader.appendChild(fromField);
            }
            
            // To field
            if (email.to) {
                const toField = document.createElement('div');
                toField.classList.add('email-field');
                toField.innerHTML = `<strong>To:</strong> ${email.to}`;
                emailHeader.appendChild(toField);
            }
            
            // CC field
            if (email.cc) {
                const ccField = document.createElement('div');
                ccField.classList.add('email-field');
                ccField.innerHTML = `<strong>CC:</strong> ${email.cc}`;
                emailHeader.appendChild(ccField);
            }
            
            // BCC field
            if (email.bcc) {
                const bccField = document.createElement('div');
                bccField.classList.add('email-field');
                bccField.innerHTML = `<strong>BCC:</strong> ${email.bcc}`;
                emailHeader.appendChild(bccField);
            }
            
            // Subject field
            if (email.subject) {
                const subjectField = document.createElement('div');
                subjectField.classList.add('email-field', 'email-subject');
                subjectField.innerHTML = `<strong>Subject:</strong> ${email.subject}`;
                emailHeader.appendChild(subjectField);
            }
            
            // Date field
            if (email.date) {
                const dateField = document.createElement('div');
                dateField.classList.add('email-field');
                dateField.innerHTML = `<strong>Date:</strong> ${email.date}`;
                emailHeader.appendChild(dateField);
            }
            
            // Reply-To field
            if (email.reply_to) {
                const replyToField = document.createElement('div');
                replyToField.classList.add('email-field');
                replyToField.innerHTML = `<strong>Reply-To:</strong> ${email.reply_to}`;
                emailHeader.appendChild(replyToField);
            }
            
            // Message-ID field
            if (email.message_id) {
                const messageIdField = document.createElement('div');
                messageIdField.classList.add('email-field');
                messageIdField.innerHTML = `<strong>Message-ID:</strong> ${email.message_id}`;
                emailHeader.appendChild(messageIdField);
            }
            
            contentElement.appendChild(emailHeader);
            
            // Add separator line
            const separator = document.createElement('hr');
            separator.classList.add('email-separator');
            contentElement.appendChild(separator);
            
            // Email body
            const emailBody = document.createElement('div');
            emailBody.classList.add('email-body');
            
            // Check if any body content exists
            if (email.body_html) {
                emailBody.innerHTML = email.body_html;
            } else if (email.body_text) {
                // Convert newlines to <br> tags for proper display
                emailBody.innerHTML = email.body_text.replace(/\n/g, '<br>');
            } else if (email.body) {
                emailBody.textContent = email.body;
            } else {
                // If no body content, show a placeholder
                emailBody.textContent = '[No content]';
            }
            
            contentElement.appendChild(emailBody);
            
            // Add copy button for the entire email
            const emailText = _formatEmailAsText(email);
            _addCopyButton(messageElement, 'email', emailText, contentElement);
            
            messageElement.appendChild(contentElement);
            
            // Add attachments if present
            if (email.attachments && email.attachments.length > 0) {
                const attachmentsContainer = document.createElement('div');
                attachmentsContainer.classList.add('email-attachments');
                
                const attachmentsTitle = document.createElement('h4');
                attachmentsTitle.textContent = 'Attachments:';
                attachmentsContainer.appendChild(attachmentsTitle);
                
                email.attachments.forEach(attachment => {
                    const attachmentElement = document.createElement('div');
                    attachmentElement.classList.add('email-attachment');
                    attachmentElement.innerHTML = `
                        <i class="fa fa-paperclip"></i>
                        <span>${attachment.filename || attachment.name || 'Unknown file'}</span>
                        ${attachment.size ? `<span class="attachment-size">(${_formatFileSize(attachment.size)})</span>` : ''}
                    `;
                    attachmentsContainer.appendChild(attachmentElement);
                });
                
                contentElement.appendChild(attachmentsContainer);
            }
            
            _addJsonViewer(messageElement, embeddedJson);
            
            DOM.chatBox.appendChild(messageElement);
            UI.scrollToBottom();
            return messageElement;
        }

        function _formatEmailAsText(email) {
            let text = '';
            
            if (email.from) text += `From: ${email.from}\n`;
            if (email.to) text += `To: ${email.to}\n`;
            if (email.cc) text += `CC: ${email.cc}\n`;
            if (email.bcc) text += `BCC: ${email.bcc}\n`;
            if (email.subject) text += `Subject: ${email.subject}\n`;
            if (email.date) text += `Date: ${email.date}\n`;
            if (email.reply_to) text += `Reply-To: ${email.reply_to}\n`;
            if (email.message_id) text += `Message-ID: ${email.message_id}\n`;
            
            text += '\n';
            
            if (email.body_html) {
                // Strip HTML tags for plain text version
                text += email.body_html.replace(/<[^>]*>/g, '');
            } else if (email.body_text) {
                text += email.body_text;
            } else if (email.body) {
                text += email.body;
            }
            
            if (email.attachments && email.attachments.length > 0) {
                text += '\n\nAttachments:\n';
                email.attachments.forEach(attachment => {
                    text += `- ${attachment.filename || attachment.name || 'Unknown file'}`;
                    if (attachment.size) {
                        text += ` (${_formatFileSize(attachment.size)})`;
                    }
                    text += '\n';
                });
            }
            
            return text;
        }

        function _formatFileSize(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        
        function _createConversationElement() {
            const conversationElement = document.createElement('div');
           // conversationElement.classList.add('conversation');
            conversationElement.classList.add('message');
            conversationElement.classList.add('assistant-message');
            conversationElement.classList.add('voice-expert');
            return conversationElement;
        }

        function _createConversationMessageElement(contents) {

            // Create a new div element for the conversation message. The div should have a grid layout with 3 columns. 
            // The first row should have the sender_name, timestamp and source. 
            // The second row should have the one column that spans the threecontent with the  content

            try {

                // 1. Create the main container
                const myContainer = document.createElement('div');
                myContainer.classList.add('conversation-message');


                // 2. Create the top row
                const topRow = document.createElement('div');
                topRow.classList.add('conversation-row', 'conversation-top-row');

                // 3. Create items for the top row using the 'contents' object
                // Item 1
                const topItem1 = document.createElement('div');
                topItem1.classList.add('conversation-item');
                // Sanitize sender_name to only alphanumeric characters
                let safeSenderName = (contents.sender_name || 'Default Item 1 (Bold)').replace(/[^a-zA-Z0-9 ]/g, '');
                topItem1.innerHTML = `<strong>${safeSenderName}</strong>`;

                // Item 2
                const topItem2 = document.createElement('div');
                topItem2.classList.add('conversation-item');
                topItem2.textContent = contents.sent_at || '-';

                // Item 3
                const topItem3 = document.createElement('div');
                topItem3.classList.add('conversation-item');
                topItem3.textContent = contents.source || 'Default Item 3';

                // 4. Append top items to the top row
                topRow.appendChild(topItem1);
                topRow.appendChild(topItem2);
                topRow.appendChild(topItem3);

                // 5. Create the bottom row
                const bottomRow = document.createElement('div');
                bottomRow.classList.add('conversation-row', 'conversation-bottom-row');

                // 6. Create item for the bottom row using the 'contents' object
                const bottomItem = document.createElement('div');
                bottomItem.classList.add('conversation-item', 'conversation-full-width-item');
               

                // 7. Append bottom item to the bottom row
                if (contents.attachments && contents.attachments.length > 0) {
                    _addImagePreviews(bottomItem, contents);
                } else {
                    bottomItem.textContent = contents.content || 'Default Full Width Item';
                }

                bottomRow.appendChild(bottomItem);

                // 8. Append rows to the main container
                myContainer.appendChild(topRow);
                myContainer.appendChild(bottomRow);

                // 9. Return the created container
                return myContainer;

            } catch (error) {
                console.error('Error creating conversation message element:', error);
                return null;
            }
        }


        function addConversation(messagesData) {
            const conversationElement = _createConversationElement();

            for (const conversation of messagesData) {
                for (const message of conversation.messages) {
                const messageElement =_createConversationMessageElement(message);
                conversationElement.appendChild(messageElement);
                }
            }
            
            DOM.chatBox.appendChild(conversationElement);
            UI.scrollToBottom();
            return conversationElement;
        }

        function clearChat() {
            DOM.chatBox.innerHTML = '';
            DOM.infoBox.classList.remove('hidden');
            DOM.chatBox.appendChild(DOM.infoBox); // Re-add info box if it's part of chatBox
        }

        function renderExistingMessages() {
            DOM.chatBox.querySelectorAll('.message .message-content').forEach(contentElement => {
                const rawText = contentElement.textContent; // Or from raw-markdown if it exists
                const role = contentElement.dataset.role;
                if (role === 'assistant' || role === 'model') {
                    renderMarkdown(contentElement, rawText);
                } // User messages are already plain text
            });
            UI.scrollToBottom();
        }

        return { addMessage, clearChat, addConversation, renderExistingMessages, renderMarkdown, addEmail };
    })();

    // --- API Service Module ---
    const ApiService = (() => {
        async function _fetch(url, options) {
            const response = await fetch(url, options);
            if (!response.ok) {
                let errorMsg = `HTTP error! Status: ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.error || errorMsg;
                } catch (e) {
                    const textError = await response.text();
                    errorMsg = textError || errorMsg;
                }
                throw new Error(errorMsg);
            }
            return response;
        }

        async function fetchChat(payload) {

            if(payload.interviewMode) {
                return _fetch(CONSTANTS.API_PATHS.INTERVIEW, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
            } 
            else {
                return _fetch(CONSTANTS.API_PATHS.CHAT, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                }); // Returns the raw response for streaming/json handling by caller
            }
        }

        async function fetchNewChat(payload) {

                return _fetch(CONSTANTS.API_PATHS.NEW_CHAT, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                }); // Returns the raw response for streaming/json handling by caller
            
        }

        async function startInterview() {
            return _fetch(CONSTANTS.API_PATHS.NEW_INTERVIEW, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
        }

        async function checkInterviewData() {
            return _fetch(CONSTANTS.API_PATHS.CHECK_INTERVIEW_DATA, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
        }

        async function pauseInterview() {
            return _fetch(CONSTANTS.API_PATHS.PAUSE_INTERVIEW, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
        }

        async function resumeInterview() {
            return _fetch(CONSTANTS.API_PATHS.RESUME_INTERVIEW, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
        }

        async function finishInterview() {
            return _fetch(CONSTANTS.API_PATHS.FINISH_INTERVIEW, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
        }

        async function writeInterimBio() {

            return _fetch(CONSTANTS.API_PATHS.WRITE_INTERIM_BIO, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
        }

        async function writeFinalBio() {

            return _fetch(CONSTANTS.API_PATHS.WRITE_FINAL_BIO, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
        }

        async function resetInterview() {
            return _fetch('/interviewer/resetinterview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
        }

        async function fetchVoice(payload) {
            const response = await _fetch(CONSTANTS.API_PATHS.VOICE, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            return response.blob();
        }
        
        async function fetchSuggestionsConfig() {
            const response = await _fetch(CONSTANTS.API_PATHS.SUGGESTIONS_JSON);
            return response.json();
        }

        async function fetchFacebookChatters() {
            const response = await _fetch(CONSTANTS.API_PATHS.FB_CHATTERS);
            return response.json();
        }

        async function fetchContacts() {
            const response = await _fetch(CONSTANTS.API_PATHS.CONTACTS);
            return response.json();
        }
        
        async function fetchMessagesByContact(name, one_to_one_only) {
             const response = await _fetch(CONSTANTS.API_PATHS.MESSAGES_BY_CONTACT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, one_to_one_only })
            });
            return response.json();
        }
        async function fetchMessagesByContactV2(name, one_to_one_only) {
            const url = CONSTANTS.API_PATHS.MESSAGES_BY_CONTACT_V2 + name;
            const response = await _fetch(url, {
               method: 'GET',
               headers: { 'Content-Type': 'application/json' }
           });
           return response.json();
       }

        async function fetchAlbums() {
            const response = await _fetch(CONSTANTS.API_PATHS.ALBUMS);
            return response.json();
        }

        return {
            fetchChat, fetchNewChat, fetchVoice, fetchSuggestionsConfig,
            fetchFacebookChatters, fetchContacts, fetchMessagesByContact, fetchAlbums, fetchMessagesByContactV2,
            startInterview, checkInterviewData, pauseInterview, resumeInterview, finishInterview, writeInterimBio, writeFinalBio, resetInterview
        };
    })();

    // --- Voice Selector Module ---
    const VoiceSelector = (() => {
        function getSelectedVoice() {
            const voiceSelect = document.getElementById('voice-select');
            return voiceSelect ? voiceSelect.value : 'expert'; // Default to expert
        }

        function updateLoadingIndicatorImage() {
            const selectedVoice = getSelectedVoice();
            if (DOM.loadingVoiceImage) {
                DOM.loadingVoiceImage.src = `/static/images/${CONSTANTS.VOICE_IMAGES[selectedVoice + '_sm']}`;
                DOM.loadingVoiceImage.alt = `${selectedVoice} character`;
            }
        }

        function updateVoicePreview(voiceName) {
            console.log('updateVoicePreview called with voiceName:', voiceName);
            if (DOM.voicePreviewImg) {
                const imageName = CONSTANTS.VOICE_IMAGES[voiceName];
                console.log('Image name from CONSTANTS:', imageName);
                if (imageName) {
                    const imagePath = `/static/images/${imageName}`;
                    console.log('Setting image src to:', imagePath);
                    DOM.voicePreviewImg.src = imagePath;
                    DOM.voicePreviewImg.alt = `${voiceName} character`;
                    
                    // Test if image loads
                    DOM.voicePreviewImg.onload = () => {
                        console.log('Voice preview image loaded successfully');
                    };
                    DOM.voicePreviewImg.onerror = () => {
                        console.error('Failed to load voice preview image:', imagePath);
                    };
                } else {
                    console.warn(`Voice image not found for: ${voiceName}`);
                }
            } else {
                console.error('voicePreviewImg element not found!');
            }
            if (DOM.voicePreviewDesc) {
                DOM.voicePreviewDesc.textContent = CONSTANTS.VOICE_DESCRIPTIONS[voiceName] || '';
            } else {
                console.error('voicePreviewDesc element not found!');
            }
        }

        function updateSelectedVoiceImage(voiceName) {
            if (DOM.selectedVoiceImage) {
                DOM.selectedVoiceImage.src = `/static/images/${CONSTANTS.VOICE_IMAGES[voiceName]}`;
                DOM.selectedVoiceImage.alt = `${voiceName} character`;
            }
        }

        function _handleVoiceChange(event) {
            const newVoice = event.target.value;
            updateLoadingIndicatorImage();
            updateVoicePreview(newVoice);
            updateSelectedVoiceImage(newVoice);

            if (newVoice === 'expert') {
                if (DOM.creativityLevel) {
                    DOM.creativityLevel.value = 0;
                    DOM.creativityLevel.disabled = true;
                }
            } else if (['irish', 'earthchild', 'haiku', 'insult', 'secret_admirer'].includes(newVoice)) {
                if (DOM.creativityLevel) {
                    DOM.creativityLevel.value = 2.0;
                    DOM.creativityLevel.disabled = false;
                }
            } else {
                if (DOM.creativityLevel) {
                    DOM.creativityLevel.value = 0.5;
                    DOM.creativityLevel.disabled = false;
                }
            }
            if(DOM.creativityLevel && DOM.creativityLevel.nextElementSibling) DOM.creativityLevel.nextElementSibling.textContent = DOM.creativityLevel.value;

            Config.saveSettings(); // Save new creativity level

            if (DOM.moodSelector) {
                DOM.moodSelector.style.display = newVoice === 'dave' ? 'block' : 'none';
            }
            
            // Chat.clearChat();
            // UI.clearError();
            UI.hideLoadingIndicator();
            if (DOM.userInput) DOM.userInput.value = '';
            Chat.addMessage('assistant', "Voice changed to " + CONSTANTS.VOICE_DESCRIPTIONS[newVoice], true, null, null);
        }

        function highlightSelectedVoiceIcon() {
            const selectedVoice = getSelectedVoice();
            DOM.voiceIcons.forEach(img => {
                const alt = img.alt.toLowerCase().replace(/[-_]/g, '');
                const val = selectedVoice.toLowerCase().replace(/[-_]/g, '');
                img.style.border = (alt === val) ? '3px solid blue' : 'none';
            });
        }
        
        function setInitialState() {
            const initialVoice = getSelectedVoice();
            console.log('Setting initial voice:', initialVoice);
            updateVoicePreview(initialVoice); // Update preview for initial voice
            updateSelectedVoiceImage(initialVoice); // Update selected voice image
            if (initialVoice === 'expert') {
                if (DOM.creativityLevel) {
                    DOM.creativityLevel.value = 0;
                    DOM.creativityLevel.disabled = true;
                }
            } else {
                // Ensure creativity is enabled if not expert, using its current value or a default
                if (DOM.creativityLevel) {
                    DOM.creativityLevel.disabled = false; 
                }
            }
            if(DOM.creativityLevel && DOM.creativityLevel.nextElementSibling) DOM.creativityLevel.nextElementSibling.textContent = DOM.creativityLevel.value;
            highlightSelectedVoiceIcon();
            updateLoadingIndicatorImage(); // Also set initial loading indicator image
        }

        function init() {
            setInitialState();
            // Add event listener for the voice select dropdown
            if (DOM.voiceSelect) {
                DOM.voiceSelect.addEventListener('change', (e) => {
                    _handleVoiceChange(e);
                    highlightSelectedVoiceIcon(); // Also update highlight on change
                });
            }
            DOM.voiceIconWrappers.forEach(wrapper => {
                wrapper.addEventListener('click', () => {
                    const voice = wrapper.dataset.voice;
                    if (DOM.voiceSelect) {
                        DOM.voiceSelect.value = voice;
                        // Manually dispatch change event to trigger all handlers
                        DOM.voiceSelect.dispatchEvent(new Event('change', { bubbles: true })); 
                    }
                });
            });
        }
        return { init, getSelectedVoice, updateLoadingIndicatorImage, updateVoicePreview, updateSelectedVoiceImage };
    })();

    // --- Modals ---
    const Modals = {
        _openModal: (modalElement) => { modalElement.style.display = 'flex'; },
        _closeModal: (modalElement) => { modalElement.style.display = 'none'; },

        Suggestions: (() => {
            function open() {
                Modals._openModal(DOM.suggestionsModal);
                DOM.suggestionsListContainer.innerHTML = '<div>Loading...</div>';
                ApiService.fetchSuggestionsConfig()
                    .then(data => {
                        DOM.suggestionsListContainer.innerHTML = '';
                        if (data.categories && Array.isArray(data.categories)) {
                            data.categories.forEach(cat => {
                                if (Array.isArray(cat.suggestions)) {
                                    cat.suggestions.forEach(sugg => {
                                        const suggTile = document.createElement('div');
                                        suggTile.style.backgroundColor = '#ffffff';
                                        suggTile.style.display = 'flex';
                                        suggTile.style.flexDirection = 'column';
                                        suggTile.style.height = '120px';
                                        suggTile.style.gap = '0';


                                        const catTitle = document.createElement('p');
                                        catTitle.innerText = cat.category;
                                        catTitle.style.fontFamily = 'Arial, sans-serif';
                                        catTitle.style.fontWeight = 'bold';
                                        catTitle.style.margin = '0';
                                        catTitle.style.flex = '1 1 0%';
                                        catTitle.style.display = 'flex';
                                        catTitle.style.alignItems = 'center';
                                        catTitle.style.justifyContent = 'center';


                                        const suggestionTitle = document.createElement('p');
                                        suggestionTitle.innerText = sugg.title;
                                        suggestionTitle.style.margin = '0';
                                        suggestionTitle.style.flex = '2 1 0%';
                                        suggestionTitle.style.display = 'flex';
                                        suggestionTitle.style.alignItems = 'center';
                                        suggestionTitle.style.justifyContent = 'center';


                                        suggTile.appendChild(catTitle);
                                        suggTile.appendChild(suggestionTitle);
                                        suggTile.classList.add('tile-suggestions');
                                        suggTile.addEventListener('click', () => {
                                            Modals._closeModal(DOM.suggestionsModal);
                                            if (sugg.function && AppActions[sugg.function]) {
                                                AppActions[sugg.function]();
                                            } else {
                                                App.processFormSubmit(sugg.prompt, cat.category, sugg.title);
                                            }
                                        });
                                        DOM.suggestionsListContainer.appendChild(suggTile);
                                    });
                                }
                            });
                        } else {
                            DOM.suggestionsListContainer.innerHTML = '<div>No suggestions found.</div>';
                        }
                    })
                    .catch(err => {
                        console.error("Failed to load suggestions:", err);
                        DOM.suggestionsListContainer.innerHTML = '<div>Failed to load suggestions.</div>';
                        UI.displayError("Could not load suggestions: " + err.message);
                    });
            }
            function close() { Modals._closeModal(DOM.suggestionsModal); }
            function init() {
           //     DOM.suggestionsBtn.addEventListener('click', open);
                DOM.closeSuggestionsModalBtn.addEventListener('click', close);
                DOM.suggestionsModal.addEventListener('click', (e) => { if (e.target === DOM.suggestionsModal) close(); });
            }
            return { init, open };
        })(),

        FBAlbums: (() => {
            async function open() {
                Modals._openModal(DOM.fbAlbumsModal);
                DOM.fbAlbumsSelect.disabled = true;
                DOM.fbAlbumsSelect.innerHTML = '<option value="">Loading...</option>';
                DOM.fbAlbumsOkBtn.disabled = true;

                try {
                    const data = await ApiService.fetchAlbums();
                    DOM.fbAlbumsSelect.innerHTML = '<option value="">Select Album</option>';
                    for (const album of data) { // Assuming data is an array
                        const option = document.createElement('option');
                        // Store unique identifier. Here, combining name and description.
                        // Or better, if album has an ID, use that. For now, stringified version.
                        option.value = JSON.stringify({ name: album.name, description: album.description, attachments: album.attachments });
                        option.textContent = `${album.name} (${album.number_of_photos} photos)`;
                        DOM.fbAlbumsSelect.appendChild(option);
                    }
                } catch (error) {
                    console.error("Failed to load FB albums:", error);
                    DOM.fbAlbumsSelect.innerHTML = '<option value="">Failed to load albums</option>';
                    UI.displayError("Could not load FB albums: " + error.message);
                } finally {
                    DOM.fbAlbumsSelect.disabled = false;
                }
            }
            function close() { 
                Modals._closeModal(DOM.fbAlbumsModal); 
                Modals._closeModal(DOM.fbImageModal);
            }

            function handleSubmit() {
                const selectedAlbumValue = DOM.fbAlbumsSelect.value;
                if (!selectedAlbumValue) return;
                try {
                    const albumData = JSON.parse(selectedAlbumValue);
                    close();
                    _showTileModal(albumData.name, albumData.description, albumData.attachments);
                } catch (e) {
                    console.error("Error parsing album data from select: ", e);
                    UI.displayError("Invalid album data selected.");
                }
            }

            function _showTileModal(title, description, tiles) { // tiles are {uri, description}
                if (!DOM.fbImageModal || !DOM.fbImageModalTitle || !DOM.fbImageModalDescription || !DOM.fbImageContainer) {
                    console.error('Tile album modal elements not found');
                    return;
                }
                DOM.fbImageModalTitle.textContent = title;
                DOM.fbImageModalDescription.textContent = description;
                DOM.fbImageContainer.innerHTML = ''; // Clear existing tiles

                tiles.forEach((tileData, index) => {
                    const tileElement = document.createElement('div');
                    tileElement.className = 'tile-album';
                    const img = document.createElement('img');
                    img.src =  "/getImage?id="+tileData.file_id+"&preview=true&resize_to=200"; // Assuming uri is the direct image source
                    img.alt = tileData.photo_description;
                    img.loading = 'lazy';
                    const desc = document.createElement('div');
                    desc.className = 'tile-album-description';
                    desc.textContent = tileData.description;

                    tileElement.onclick = () => Modals.MultiImageDisplay.showMultiImageModal(tiles, tileData.file_id);
                    
                    tileElement.appendChild(img);
                    tileElement.appendChild(desc);
                    DOM.fbImageContainer.appendChild(tileElement);
                });
                Modals._openModal(DOM.fbImageModal);
            }

            async function openAlbum(albumTitle) {
                const data = await ApiService.fetchAlbums();
                
                for (const album of data) { // Assuming data is an array
                    if (album.name.toLowerCase() === albumTitle.toLowerCase()) {
                        _showTileModal(album.name, album.description, album.attachments);
                    }
                }
                
            }

            function init() {
                if (DOM.closeFBAlbumsModalBtn){ 
                    DOM.closeFBAlbumsModalBtn.addEventListener('click', close); }
                if (DOM.fbAlbumsCancelBtn) DOM.fbAlbumsCancelBtn.addEventListener('click', close);
                if (DOM.fbAlbumsOkBtn) {
                    DOM.fbAlbumsOkBtn.addEventListener('click', handleSubmit);
                    DOM.fbAlbumsOkBtn.disabled = true; // Initial state
                }
                if (DOM.fbImageModalCloseBtn) DOM.fbImageModalCloseBtn.addEventListener('click', close);
                if (DOM.fbAlbumsSelect) {
                     DOM.fbAlbumsSelect.addEventListener('change', () => {
                        DOM.fbAlbumsOkBtn.disabled = !(DOM.fbAlbumsSelect.value && DOM.fbAlbumsSelect.value !== '');
                    });
                }
                if (DOM.fbAlbumsModal) DOM.fbAlbumsModal.addEventListener('click', (e) => { if (e.target === DOM.fbAlbumsModal) close(); });
            }
            return { init, open, openAlbum };
        })(),
        
        HaveYourSay: (() => {
            function open() {
                Modals._openModal(DOM.haveYourSayModal);
                DOM.haveYourSayTextarea.value = '';
                DOM.dictationStatus.textContent = '';
                // DOM.haveYourSayTextarea.focus(); // Can be disruptive
            }
            function close() {
                Modals._closeModal(DOM.haveYourSayModal);
                stopDictation();
            }

            function startDictation() {
                if (!AppState.dictationRecognition) return;
                if (AppState.isDictationListening) {
                    stopDictation();
                    return;
                }
                AppState.finalDictationTranscript = '';
                DOM.haveYourSayTextarea.value = '';
                AppState.dictationRecognition.start();
                DOM.startDictationBtn.style.display = 'none';
                DOM.stopDictationBtn.style.display = 'block';
            }

            function stopDictation() {
                if (AppState.dictationRecognition && AppState.isDictationListening) {
                    AppState.dictationRecognition.stop();
                    // isListening will be set to false by onend
                }
                // Explicitly ensure button state is correct even if onend is delayed
                DOM.dictationStatus.textContent = 'Dictation stopped.';
                DOM.stopDictationBtn.style.display = 'none';
                DOM.startDictationBtn.style.display = 'block';
                AppState.isDictationListening = false;
            }
            
            function handleSubmit() {
                const text = DOM.haveYourSayTextarea.value.trim();
                const name = DOM.haveYourSayName.value.trim();
                const relationship = DOM.haveYourSayRelationship.value.trim();
                let prefix = '';
                if (name && relationship) prefix = `${name} (${relationship}): `;
                else if (name) prefix = `${name}: `;
                else if (relationship) prefix = `(${relationship}): `;
                
                if (text) {
                    // DOM.userInput.value = prefix + text;
                    // close();
                    // DOM.userInput.focus();
                   
                fetch(CONSTANTS.API_PATHS.HAVE_YOUR_SAY, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        content: text,
                        name: name,
                        relationship: relationship
                    })
                })
                .then(response => {
                    if (response.ok) {
                        DOM.dictationStatus.textContent = 'Thank you for your submission!';
                        close();
                        DOM.userInput.focus();
                    } else {
                        DOM.dictationStatus.textContent = 'Error submitting. Please try again.';
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    DOM.dictationStatus.textContent = 'Error submitting. Please try again.';
                });
                } else {
                    DOM.dictationStatus.textContent = 'Please enter or dictate some text.';
                }
            }

            function initSpeechRecognition() {
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                if (SpeechRecognition) {
                    AppState.dictationRecognition = new SpeechRecognition();
                    AppState.dictationRecognition.lang = 'en-US';
                    AppState.dictationRecognition.interimResults = true;
                    AppState.dictationRecognition.continuous = true;

                    AppState.dictationRecognition.onstart = () => { AppState.isDictationListening = true; DOM.dictationStatus.textContent = 'Listening...'; };
                    AppState.dictationRecognition.onerror = (event) => { DOM.dictationStatus.textContent = 'Dictation error: ' + event.error; AppState.isDictationListening = false; stopDictation(); };
                    AppState.dictationRecognition.onend = () => { AppState.isDictationListening = false; if (DOM.dictationStatus.textContent === 'Listening...') DOM.dictationStatus.textContent = 'Dictation stopped.'; stopDictation();}; // Ensure stop UI updates
                    AppState.dictationRecognition.onresult = (event) => {
                        let interimTranscript = '';
                        for (let i = event.resultIndex; i < event.results.length; ++i) {
                            if (event.results[i].isFinal) AppState.finalDictationTranscript += event.results[i][0].transcript;
                            else interimTranscript += event.results[i][0].transcript;
                        }
                        DOM.haveYourSayTextarea.value = AppState.finalDictationTranscript + interimTranscript;
                    };
                } else {
                    DOM.startDictationBtn.disabled = true;
                    DOM.dictationStatus.textContent = 'Speech recognition not supported.';
                }
            }

            // Chat dictation functions
            function startChatDictation() {
                if (!AppState.chatDictationRecognition) return;
                if (AppState.isChatDictationListening) {
                    stopChatDictation();
                    return;
                }
                AppState.finalChatDictationTranscript = '';
                DOM.userInput.value = '';
                AppState.chatDictationRecognition.start();
                DOM.chatStartDictationBtn.style.display = 'none';
                DOM.chatStopDictationBtn.style.display = 'block';
            }

            function stopChatDictation() {
                // Prevent double execution by checking if already stopped
                if (!AppState.isChatDictationListening) {
                    return;
                }
                
                if (AppState.chatDictationRecognition) {
                    AppState.chatDictationRecognition.stop();
                }
                DOM.chatStopDictationBtn.style.display = 'none';
                DOM.chatStartDictationBtn.style.display = 'block';
                AppState.isChatDictationListening = false;
                
                // Auto-submit the entered text if there's content
                const userInput = DOM.userInput.value.trim();
                if (userInput) {
                    // Trigger the form submission
                    // const chatForm = document.getElementById('chat-form');
                    // if (chatForm) {
                    //     chatForm.dispatchEvent(new Event('submit', { bubbles: true }));
                    // }
                    App.processFormSubmit(userInput);
                }
            }

            function initChatSpeechRecognition() {
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                if (SpeechRecognition) {
                    AppState.chatDictationRecognition = new SpeechRecognition();
                    AppState.chatDictationRecognition.lang = 'en-US';
                    AppState.chatDictationRecognition.interimResults = true;
                    AppState.chatDictationRecognition.continuous = true;

                    AppState.chatDictationRecognition.onstart = () => { 
                        AppState.isChatDictationListening = true; 
                    };
                    AppState.chatDictationRecognition.onerror = (event) => { 
                        DOM.chatDictationStatus.textContent = 'Dictation error: ' + event.error; 
                        AppState.isChatDictationListening = false; 
                        stopChatDictation(); 
                    };
                    AppState.chatDictationRecognition.onend = () => { 
                        // Only call stopChatDictation if we're still listening
                        // This prevents double execution when manually stopping
                        if (AppState.isChatDictationListening) {
                            stopChatDictation(); 
                        }
                    };
                    AppState.chatDictationRecognition.onresult = (event) => {
                        let interimTranscript = '';
                        for (let i = event.resultIndex; i < event.results.length; ++i) {
                            if (event.results[i].isFinal) {
                                AppState.finalChatDictationTranscript += event.results[i][0].transcript;
                            } else {
                                interimTranscript += event.results[i][0].transcript;
                            }
                        }
                        DOM.userInput.value = AppState.finalChatDictationTranscript + interimTranscript;
                    };
                } else {
                    if (DOM.chatStartDictationBtn) {
                        DOM.chatStartDictationBtn.disabled = true;
                        DOM.chatDictationStatus.textContent = 'Speech recognition not supported.';
                    }
                }
            }

            function init() {
                if (DOM.haveYourSayBtn) DOM.haveYourSayBtn.addEventListener('click', open);
                if (DOM.closeHaveYourSayModalBtn) DOM.closeHaveYourSayModalBtn.addEventListener('click', close);
                if (DOM.cancelHaveYourSayBtn) DOM.cancelHaveYourSayBtn.addEventListener('click', close);
                if (DOM.haveYourSayModal) DOM.haveYourSayModal.addEventListener('click', (e) => { if (e.target === DOM.haveYourSayModal) close(); });
                
                initSpeechRecognition();
                if (DOM.startDictationBtn) DOM.startDictationBtn.addEventListener('click', startDictation);
                if (DOM.stopDictationBtn) DOM.stopDictationBtn.addEventListener('click', stopDictation);
                if (DOM.submitHaveYourSayBtn) DOM.submitHaveYourSayBtn.addEventListener('click', handleSubmit);

                // Initialize chat dictation
                initChatSpeechRecognition();
                if (DOM.chatStartDictationBtn) DOM.chatStartDictationBtn.addEventListener('click', startChatDictation);
                if (DOM.chatStopDictationBtn) DOM.chatStopDictationBtn.addEventListener('click', stopChatDictation);
            }
            return { init,open };
        })(),

        Locations: (() => {

            let geoData = [];
            let photoPlacesData = [];
            let mapViewInitialized = false;

            let selectedIdx = -1;
            let map = null;
            let mapView = null;
            let photoMarkersLayer = null;
            let currentPhotoIndex = 0;
            let layerControl = null;

            function init() {
                if (DOM.geoMapFixedBtn) DOM.geoMapFixedBtn.addEventListener('click', _openGeoMapInNewTab);
                if (DOM.closeGeoMetadataModalBtn) DOM.closeGeoMetadataModalBtn.addEventListener('click', close);
                if (DOM.shufflePhotosBtn) DOM.shufflePhotosBtn.addEventListener('click', shufflePhotoMarkers);
            }

            function _createPhotoMarkers() {
                let photoMarkers = [];
                let photoShown = 0;
                
                // Generate a new random starting index
                currentPhotoIndex = Math.floor(Math.random() * 8);
                
                geoData.forEach(item => {
                    if (!item.latitude || !item.longitude) {
                        return;
                    }
                    if (item.file_id) {
                        currentPhotoIndex++;
                        if (currentPhotoIndex % 8 === 0) {  // Only show every 8th markers at a time
                            photoShown++;
                            try{
                                const marker = L.marker([item.latitude, item.longitude])
                                marker.file = item.file; // Attach file info to marker
                                marker.file_id = item.file_id;
                                marker.taken = item.date_taken;
                                marker.lat = item.latitude;
                                marker.long = item.longitude;
                                marker.on('click', function() {
                                    Modals.SingleImageDisplay.showSingleImageModal(item.file, item.file_id, item.taken, item.lat, item.long);
                                });
                                photoMarkers.push(marker);
                            } catch (e) {
                                console.error('Error adding photo place marker:', e);
                            }
                        }
                    }
                });
                
                return { photoMarkers, photoShown, currentPhotoIndex };
            }

            function shufflePhotoMarkers() {
                if (!mapView || !photoMarkersLayer || !layerControl) return;
                
                // Remove existing photo markers layer from both map and layer control
                mapView.removeLayer(photoMarkersLayer);
                layerControl.removeLayer(photoMarkersLayer);
                
                // Create new photo markers with new random starting index
                const { photoMarkers, photoShown, currentPhotoIndex } = _createPhotoMarkers();
                
                // Create new layer and add to map and layer control
                photoMarkersLayer = L.layerGroup(photoMarkers).addTo(mapView);
                layerControl.addOverlay(photoMarkersLayer, 'GPS Photos Locations ('+photoMarkers.length+')');
                
                // Update the count display
                document.getElementById('geo-metadata-shown-count').textContent = 'Showing '+photoShown+' of '+currentPhotoIndex+' photos (Shuffled!)';
            }

            function open() {
                Modals._openModal(DOM.geoMetadataModal);
                // DOM.geoList.innerHTML = '';
                if (geoData.length === 0 || photoPlacesData.length === 0) {

                    fetch('/getLocations').then(r => r.json()).then(data => {
                        geoData = data;
                        mapViewInitialized = false;
                         _initMapView();
                    });
                } else {
                    if (geoData.length > 0) _selectLocation(selectedIdx >= 0 ? selectedIdx : 0);
                }


            }
            function close() {
                Modals._closeModal(DOM.geoMetadataModal);
            }

            function openMapView() {
                open();
            }
             function _initMapView() {
                if (mapViewInitialized) {
                    setTimeout(() => { mapView.invalidateSize(); }, 100);
                    return;
                } else {
                    setTimeout(() => { mapView.invalidateSize(); }, 1000);
                }
                mapView = L.map('map-view', {
                    minZoom: 1,
                    maxZoom: 19,
                });
                L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    maxZoom: 19,
                    attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                }).addTo(mapView);

                // Add all markers and fit bounds
                const latlngs = geoData.map(item => [item.latitude, item.longitude]);
                if (latlngs.length > 0) {
                    mapView.fitBounds(latlngs, { padding: [20, 20] });
                }
                layerControl = L.control.layers().addTo(mapView);
                mapView.invalidateSize();

                var darkBlueMarker = L.icon({
                    iconUrl: '/static/images/marker-dark-blue.png',
                    iconSize: [25, 35],
                    iconAnchor: [12, 32],
                    popupAnchor: [0, -32]
                });

                let biographyMarkers = [];
                let fbMarkers = []
                let otherMarkers = []
                
                // Create photo markers using the extracted function
                const { photoMarkers, photoShown, currentPhotoIndex } = _createPhotoMarkers();
                
                geoData.forEach(item => {
                    if (!item.latitude || !item.longitude) {
                        return;
                    }
                    if (!item.file_id) { // Only process non-photo items here since photos are handled above
                        if (item.source === 'biography') {
                             if (item.latitude && item.longitude) {
                                 const marker = L.marker([item.latitude, item.longitude], {icon: darkBlueMarker});
                                 marker.bindPopup(item.destination);  
                                 biographyMarkers.push(marker);
                             }
                        } else if (item.source === 'Facebook') {
                                const marker = L.marker([item.latitude, item.longitude], {icon: darkBlueMarker});
                                marker.bindPopup(item.destination);
                                fbMarkers.push(marker);
                        } else {
                                const marker = L.marker([item.latitude, item.longitude]);
                                // marker.bindPopup(item.label_values.find(v => v.label === 'Place name').value);
                                // marker.place = item; // Attach place info to marker
                                otherMarkers.push(marker);
                        }
                    }
                });
                 
                 photoMarkersLayer = L.layerGroup(photoMarkers).addTo(mapView);
                 layerControl.addOverlay(photoMarkersLayer, 'GPS Photos Locations ('+photoMarkers.length+')');
                 var biographyMarkersLayer = L.layerGroup(biographyMarkers).addTo(mapView);
                 layerControl.addOverlay(biographyMarkersLayer, 'Biography Locations ('+biographyMarkers.length+')');
                 var fbMarkersLayer = L.layerGroup(fbMarkers).addTo(mapView);
                 layerControl.addOverlay(fbMarkersLayer, 'Facebook Locations ('+fbMarkers.length+')');
                 var otherMarkersLayer = L.layerGroup(otherMarkers).addTo(mapView);
                 layerControl.addOverlay(otherMarkersLayer, 'Other Locations ('+otherMarkers.length+')');

                mapView.invalidateSize();

                mapViewInitialized = true;

                document.getElementById('geo-metadata-shown-count').textContent = 'Showing '+photoShown+' of '+currentPhotoIndex+' photos (Click Shuffle Photos to see different images)' ;
                // setTimeout(() => { mapView.invalidateSize(); }, 100);
            }

             return { init,open,openMapView,shufflePhotoMarkers};
        })(),

        ImageGallery: (() => {
            let metaData = {};
            let selectedSource = '';
            let selectedYear = '';
            let selectedMonth = '';
            let searchQuery = '';
            let selectedLocation = '';
            let imageData = [];
            let map = null;
            let currentMarker = null;
            let selectedIdx = null;
            let searchTimeout = null;
            let currentImageGalleryFileInfo = null; // Store current file information for download

            function init() {
                DOM.imageGalleryModal.addEventListener('click', function(e) {
                    if (e.target === DOM.imageGalleryModal) DOM.imageGalleryModal.style.display = 'none';
                });
                DOM.closeImageGalleryModalBtn.addEventListener('click', function() {
                    DOM.imageGalleryModal.style.display = 'none';
                    close();
                });
                // if (DOM.imageGallerySourceFilter) DOM.imageGallerySourceFilter.addEventListener('change', _handleSourceFilterChange);
                // if (DOM.imageGalleryYearFilter) DOM.imageGalleryYearFilter.addEventListener('change', _handleYearFilterChange);
                // if (DOM.imageGalleryMonthFilter) DOM.imageGalleryMonthFilter.addEventListener('change', _handleMonthFilterChange);
                // if (DOM.imageGalleryLocationFilter) DOM.imageGalleryLocationFilter.addEventListener('change', _handleLocationFilterChange);
               if (DOM.imageGalleryFixedBtn) DOM.imageGalleryFixedBtn.addEventListener('click', _openGeoMapInNewTab);
                if (DOM.imageGallerySearchBtn) DOM.imageGallerySearchBtn.addEventListener('click', _handleSearch);
                if (DOM.imageGalleryClearBtn) DOM.imageGalleryClearBtn.addEventListener('click', _handleClear);
                if (DOM.downloadImageGalleryBtn) DOM.downloadImageGalleryBtn.addEventListener('click', _downloadCurrentImageGalleryItem);
                if (DOM.imageGallerySearch) {
                    DOM.imageGallerySearch.addEventListener('input', (e) => {
                        // Clear any existing timeout
                        if (searchTimeout) clearTimeout(searchTimeout);
                        
                        const query = e.target.value.trim();
                        
                        // Only search if query is at least 5 characters
                        if (query.length >= 4) {
                            // Set a new timeout to debounce the search
                            searchTimeout = setTimeout(() => {
                                searchQuery = query;
                                // Disable other filters when searching
                                DOM.imageGallerySourceFilter.disabled = true;
                                DOM.imageGalleryYearFilter.disabled = true;
                                DOM.imageGalleryMonthFilter.disabled = true;
                                DOM.imageGalleryLocationFilter.disabled = true;
                               // _renderImageGalleryList();
                            }, 300); // 300ms debounce
                        } else if (query.length === 0) {
                            // If search is cleared, re-enable filters and reset search
                            searchTimeout = setTimeout(() => {
                                searchQuery = '';
                                DOM.imageGallerySourceFilter.disabled = false;
                                DOM.imageGalleryYearFilter.disabled = false;
                                DOM.imageGalleryMonthFilter.disabled = false;
                                DOM.imageGalleryLocationFilter.disabled = false;
                                //_renderImageGalleryList();
                            }, 300);
                        }
                    });
                }
            }
            function open() {
                DOM.imageGalleryModal.style.display = 'flex';
                fetch('/imagesmetametadata')
                        .then(r => r.json())
                        .then(data => {
                            metaData = data;
                             _setSourceFilterOptions();
                        });

                map = L.map('image-gallery-map');
                L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    maxZoom: 15,
                    attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                }).addTo(map);
            }
            function _setSourceFilterOptions() {
                const sourceFilter = DOM.imageGallerySourceFilter;
                sourceFilter.innerHTML = '';
                // Make sure all sources is first in the list
                Object.keys(metaData).forEach(source => {         
                    if (source === 'all_sources') {
                        const option = document.createElement('option');
                        option.value = "all_sources";
                        option.textContent = "All Sources";
                        sourceFilter.appendChild(option);
                    } 
                });
                Object.keys(metaData).forEach(source => {
                    
                    if (source === 'all_sources') {
                       return;
                    } else {
                        const option = document.createElement('option');
                        option.value = source;
                        option.textContent = source;
                        sourceFilter.appendChild(option);
                    }
                });
                //selectedSource = Object.keys(metaData)[0];
                selectedSource = "all_sources";
                DOM.imageGallerySourceFilter.value = selectedSource;
            //    _setYearFilterOptions();
            }
            // function _handleSourceFilterChange() {

            //     selectedSource = DOM.imageGallerySourceFilter.value;
            //     _setYearFilterOptions();
            // }
            // function _setYearFilterOptions() {

            //     DOM.imageGalleryYearFilter.innerHTML = '';
            //     const option = document.createElement('option');
            //     option.value = "0";       
            //     option.textContent = "Select Year";
            //     option.disabled = true;
            //     option.selected = true;
            //     DOM.imageGalleryYearFilter.appendChild(option);

            //     let years = [];
            //     Object.keys(metaData[selectedSource]).forEach(year => {
            //         years.push(year);
            //     });
            //     years.sort((a, b) => a - b);

            //     years.forEach(year => {
            //         const option = document.createElement('option');
            //         option.value = year;
            //         option.textContent = year;
            //         DOM.imageGalleryYearFilter.appendChild(option);
            //     });
                
            //     selectedYear = years[Math.floor(Math.random() * years.length)];
            //     DOM.imageGalleryYearFilter.value = selectedYear;
            //     _setMonthFilterOptions();
            // }

            // function _handleYearFilterChange() {
            //     selectedYear = DOM.imageGalleryYearFilter.value;
            //     _setMonthFilterOptions();
            // }

            // function _setMonthFilterOptions() {
            //     const monthFilter = DOM.imageGalleryMonthFilter;
            //     monthFilter.innerHTML = '';
            //     const option = document.createElement('option');
            //     option.value = "0";       
            //     option.textContent = "Select Month";
            //     option.disabled = true;
            //     option.selected = true;
            //     monthFilter.appendChild(option);

            //     let months = [];
            //     Object.keys(metaData[selectedSource][selectedYear]).forEach(month => {
            //         months.push(month);
            //     });
            //     months.sort((a, b) => a - b);

            //     months.forEach(month => {
            //         const option = document.createElement('option');
            //         option.value = month;
            //         option.textContent = month;
            //         monthFilter.appendChild(option);
            //     });
            //     selectedMonth = months[Math.floor(Math.random() * months.length)];
            //     DOM.imageGalleryMonthFilter.value = selectedMonth;
            //     _renderImageGalleryList();
            // }

            // function _handleMonthFilterChange() {
            //     selectedMonth = DOM.imageGalleryMonthFilter.value;
            //     _renderImageGalleryList();
            // }
            // function _handleLocationFilterChange() {
            //     let selectedLocation = DOM.imageGalleryLocationFilter.value;
            //     if (selectedLocation === 'aus' 
            //         || selectedLocation === 'dxb' 
            //         || selectedLocation === 'mea' 
            //         || selectedLocation === 'eur' 
            //         || selectedLocation === 'usa' 
            //         || selectedLocation === 'can'
            //         || selectedLocation === 'nz' 
            //         || selectedLocation === 'sa' 
            //         || selectedLocation === 'af' 
            //         || selectedLocation === 'asia'
            //         || selectedLocation === 'oth'
            //     ) {

            //         DOM.imageGallerySourceFilter.value = "all";
            //         selectedSource = "all";
            //         DOM.imageGallerySourceFilter.disabled = true;

            //         DOM.imageGalleryYearFilter.value = "0";
            //         selectedYear = "0";
            //         DOM.imageGalleryYearFilter.disabled = true;

            //         DOM.imageGalleryMonthFilter.value = "0";
            //         selectedMonth = "0";
            //         DOM.imageGalleryMonthFilter.disabled = true;
            //     } else {
            //         DOM.imageGallerySourceFilter.disabled = false;
            //         DOM.imageGalleryYearFilter.disabled = false;
            //         DOM.imageGalleryMonthFilter.disabled = false;
            //     }

            //     _renderImageGalleryList();
            // }

            function _handleSearch() {
              
                _renderImageGalleryList();
            }
            function _handleClear() {
                DOM.imageGallerySearch.value = '';
                DOM.imageGallerySourceFilter.value = 'all_sources';
                DOM.imageGalleryYearFilter.value = '0';
                DOM.imageGalleryMonthFilter.value = '0';
                DOM.imageGalleryLocationFilter.value = 'all';
                searchQuery = '';
                DOM.imageGallerySourceFilter.disabled = false;
                DOM.imageGalleryYearFilter.disabled = false;
                DOM.imageGalleryMonthFilter.disabled = false;
                DOM.imageGalleryLocationFilter.disabled = false;

                DOM.imageGalleryList.innerHTML = '';

                DOM.imageGalleryImage.style.display = 'none';
                DOM.imageGalleryVideoContainer.style.display = 'none';
                DOM.imageGalleryAudioContainer.style.display = 'none';
                DOM.imageGalleryPdfContainer.style.display = 'none'

                DOM.imageGalleryImageDetails.innerHTML = "";
                DOM.imageGalleryMap.style.display = 'none';
                DOM.imageGalleryFixedBtn.style.display = 'none';
                DOM.downloadImageGalleryBtn.style.display = 'none';

            }

            function _renderImageGalleryList() {
                DOM.imageGalleryList.innerHTML = '';

                selectedSource = DOM.imageGallerySourceFilter.value;
                selectedYear = DOM.imageGalleryYearFilter.value;
                selectedMonth = DOM.imageGalleryMonthFilter.value;
                selectedLocation = DOM.imageGalleryLocationFilter.value;
                searchQuery = DOM.imageGallerySearch.value;

          
                let url = '/imagesmetadata?placeholder=true';
                
                
                if (searchQuery) {
                    url += `&like=${encodeURIComponent(searchQuery)}`;
                } else {
                        url = '/imagesmetadata?source='+selectedSource;
                        url += '&year='+selectedYear;
                        url += '&month='+selectedMonth;
                        url += '&location='+selectedLocation;
                }

                url = url.replaceAll(" ", "%20");
 
                fetch(url)
                .then(r => r.json())
                .then(data => {
                    imageData = data.images;
                    _renderImages();
                });
            }

            function _renderImages() {
                // Clear existing images
                DOM.imageGalleryList.innerHTML = '';

                // Create an Intersection Observer
                const observer = new IntersectionObserver((entries) => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            const img = entry.target.querySelector('img');
                            if (img && img.dataset.src) {
                                img.src = img.dataset.src;
                                img.removeAttribute('data-src');
                            }
                            observer.unobserve(entry.target);
                        }
                    });
                }, {
                    root: DOM.imageGalleryList,
                    threshold: 0.1
                });

                imageData.forEach((image, idx) => {

                        const imageDiv = document.createElement('div');
                        if (image.has_gps) {
                            imageDiv.classList.add('image-gallery-has-gps');
                        } else {
                            imageDiv.classList.add('image-gallery-has-no-gps');
                        }
                       
                        // Use data-src for lazy loading
                        imageDiv.innerHTML = `<img data-src="/getImage?preview=true&id=${image.file_id}&resize_to=100" alt="${image.file.split('\\').pop()}" loading="lazy">`;
                        imageDiv.addEventListener('click', () => _selectImage(idx));
                        DOM.imageGalleryList.appendChild(imageDiv);
                        
                        // Start observing the new image div
                        observer.observe(imageDiv);
                });
            }

            function _selectImage(idx) {
                selectedIdx = idx;
                let src = `/getImage?id=${imageData[idx].file_id}`;
                
                // Store current file information for download
                currentImageGalleryFileInfo = {
                    filename: imageData[idx].file,
                    file_id: imageData[idx].file_id,
                    date_taken: imageData[idx].date_taken
                };
                
                DOM.imageGalleryInstructions.style.display = 'none';
                DOM.imageGalleryFixedBtn.style.display = 'block';

                //stop playing any audio or video
                DOM.imageGalleryAudioPlayer.pause();
                DOM.imageGalleryVideoPlayer.pause();
                DOM.imageGalleryAudioPlayer.currentTime = 0;
                DOM.imageGalleryVideoPlayer.currentTime = 0;

                if (imageData[idx].file.endsWith('.mp4')) {
                    DOM.imageGalleryImage.style.display = 'none';
                    DOM.imageGalleryAudioContainer.style.display = 'none';
                    DOM.imageGalleryPdfContainer.style.display = 'none';
                    DOM.imageGalleryVideoContainer.style.display = 'block';
                    DOM.imageGalleryVideoPlayer.src = src;
                    // Reset video to beginning when selecting a new one
                    DOM.imageGalleryVideoPlayer.currentTime = 0;
                } else if (imageData[idx].file.endsWith('.opus') || imageData[idx].file.endsWith('.m4a') || imageData[idx].file.endsWith('.mp3') || imageData[idx].file.endsWith('.wav')) {
                    DOM.imageGalleryImage.style.display = 'none';
                    DOM.imageGalleryVideoContainer.style.display = 'none';
                    DOM.imageGalleryPdfContainer.style.display = 'none';
                    DOM.imageGalleryAudioContainer.style.display = 'block';
                    DOM.imageGalleryAudioPlayer.src = src;
                    // Reset audio to beginning when selecting a new one
                    DOM.imageGalleryAudioPlayer.currentTime = 0;
                } else if (imageData[idx].file.toLowerCase().endsWith('.pdf')) {
                    DOM.imageGalleryImage.style.display = 'none';
                    DOM.imageGalleryVideoContainer.style.display = 'none';
                    DOM.imageGalleryAudioContainer.style.display = 'none';
                    DOM.imageGalleryPdfContainer.style.display = 'block';
                    // Use the PDF viewer to display the PDF
                    DOM.imageGalleryPdfViewer.src = src;
                } else {
                    DOM.imageGalleryImage.style.display = 'block';
                    DOM.imageGalleryAudioContainer.style.display = 'none';
                    DOM.imageGalleryVideoContainer.style.display = 'none';
                    DOM.imageGalleryPdfContainer.style.display = 'none';
                    DOM.imageGalleryImage.src = src;
                }
                
                try {
                    DOM.imageGalleryImageDetails.innerHTML = "<p style='font-size: 14px;margin-top: 2px;margin-bottom:1px'>"+imageData[idx].file+"</p><p style='font-size: 14px;margin-top: 3px;;margin-bottom:1px'>Taken: "+imageData[idx].date_taken+"</p>";
                } catch (e) {
                    console.error('Error setting image details:', e);
                    DOM.imageGalleryImageDetails.innerHTML = "<p>Error</p>";
                }

                if (imageData[idx].has_gps) {
                    DOM.imageGalleryMap.style.display = 'block';
                    map.setView([imageData[idx].latitude, imageData[idx].longitude], 15);
                    // Remove previous marker if it exists
                    if (currentMarker) {
                        map.removeLayer(currentMarker);
                    }
                    currentMarker = L.marker([imageData[idx].latitude, imageData[idx].longitude]).addTo(map);
                }
                else {
                    DOM.imageGalleryMap.style.display = 'none';
                    DOM.imageGalleryFixedBtn.style.display = 'none';
                }
            }

            function _openGeoMapInNewTab() {
                try {
                    let url = "https://www.google.com/maps?q="+imageData[selectedIdx].latitude+","+imageData[selectedIdx].longitude;
                    window.open(url, '_googleMaps');
                } catch (e) {
                    console.error('Error opening geo map in new tab:', e);
                }
            }

            function _downloadCurrentImageGalleryItem() {
                if (!currentImageGalleryFileInfo) {
                    console.error('No file information available for download');
                    return;
                }

                const { filename, file_id } = currentImageGalleryFileInfo;
                
                // Use the download endpoint for all file types
                let downloadUrl = `/downloadFile?id=${file_id}`;

                // Create a temporary link element to trigger download
                const link = document.createElement('a');
                link.href = downloadUrl;
                link.download = filename || 'download';
                link.target = '_blank';
                
                // Append to body, click, and remove
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }

            function close() {
                DOM.imageGalleryAudioPlayer.pause();
                DOM.imageGalleryVideoPlayer.pause();
                DOM.imageGalleryAudioPlayer.currentTime = 0;
                DOM.imageGalleryVideoPlayer.currentTime = 0;
                // Clear PDF viewer
                if (DOM.imageGalleryPdfViewer) {
                    DOM.imageGalleryPdfViewer.src = '';
                }
                // Clear current file info
                currentImageGalleryFileInfo = null;
            }

            return { init, open, close };
        })(),

        EmailGallery: (() => {
            let emailData = [];
            let selectedEmailIndex = -1;
            let currentPage = 0;
            let itemsPerPage = 20;
            let isLoading = false;
            let hasMoreData = true;
            let searchTimeout = null;

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

            function init() {
                DOM.closeEmailGalleryModalBtn.addEventListener('click', close);
                DOM.emailGallerySearchBtn.addEventListener('click', _handleSearch);
                DOM.emailGalleryClearBtn.addEventListener('click', _handleClear);
                
                // Add event listeners for filter changes with debouncing
                DOM.emailGallerySearch.addEventListener('input', (e) => {
                    // Clear any existing timeout
                    if (searchTimeout) clearTimeout(searchTimeout);
                    
                    const query = e.target.value.trim();
                    
                    // Only search if query is at least 3 characters or empty
                    if (query.length >= 3 || query.length === 0) {
                        // Set a new timeout to debounce the search
                        searchTimeout = setTimeout(() => {
                            _handleSearch();
                        }, 300); // 300ms debounce
                    }
                });
                
                DOM.emailGallerySender.addEventListener('input', (e) => {
                    if (searchTimeout) clearTimeout(searchTimeout);
                    searchTimeout = setTimeout(() => {
                        _handleSearch();
                    }, 300);
                });
                
                DOM.emailGalleryRecipient.addEventListener('input', (e) => {
                    if (searchTimeout) clearTimeout(searchTimeout);
                    searchTimeout = setTimeout(() => {
                        _handleSearch();
                    }, 300);
                });
                
                DOM.emailGalleryYearFilter.addEventListener('change', _handleSearch);
                DOM.emailGalleryMonthFilter.addEventListener('change', _handleSearch);
                DOM.emailGalleryBusinessFilter.addEventListener('change', _handleSearch);
                DOM.emailGalleryAttachmentsFilter.addEventListener('change', _handleAttachmentsFilter);
               // DOM.emailGalleryFolderFilter.addEventListener('change', _handleSearch);

                // Add scroll event listener for lazy loading
                DOM.emailGalleryList.addEventListener('scroll', _handleEmailListScroll);

                // Add keyboard navigation
                document.addEventListener('keydown', _handleKeydown);
            }

            async function open() {
                DOM.emailGalleryModal.style.display = 'flex';
                 _loadEmailData();
            }

            function close() {
                DOM.emailGalleryModal.style.display = 'none';
                selectedEmailIndex = -1;
                _clearEmailContent();
            }

            function _loadEmailData() {
                _setupFilters();

                //month equals the current month
                const currentMonth = new Date().getMonth() + 1;
                DOM.emailGalleryMonthFilter.value = currentMonth;
                const currentYear = new Date().getFullYear();
                DOM.emailGalleryYearFilter.value = currentYear;

                try {
                    const params = new URLSearchParams();
                    params.append('year', currentYear);
                    params.append('month', currentMonth);
                    
                    fetch('/emails/search?' + params.toString())
                    .then(r => r.json())
                    .then(data => {
                        // Transform response to match expected format
                        emailData = data.map(email => ({
                            id: email.id,
                            subject: email.subject || 'No Subject',
                            sender: email.from_address || 'Unknown Sender',
                            recipient: email.to_addresses || 'Unknown Recipient',
                            date: email.date ? formatDateAustralian(email.date) : 'No Date',
                            folder: email.folder || 'Unknown Folder',
                            body: email.snippet || 'No content',
                            preview: email.snippet || 'No preview',
                            attachments: email.attachment_ids.map(id => `/attachments/${id}`),
                            emailId: email.id // Store email ID for fetching full content
                        }));
                        _renderEmailList();
                        _showInstructions();
                    })
                    .catch(error => {
                        console.error('Error in fetch:', error);
                        emailData = [];
                    });

                } catch (error) {
                    console.error('Error loading email data:', error);
                    emailData = [];
                
                }
            }

            function _setupFilters() {
                // Setup year filter
               // const years = [...new Set(emailData.map(email => email.year))].sort((a, b) => b - a);

                const years = [
                    { value: 0, text: 'All Years' },
                    { value: 2032, text: '2032' },
                    { value: 2031, text: '2031' },
                    { value: 2030, text: '2030' },
                    { value: 2029, text: '2029' },
                    { value: 2028, text: '2028' },
                    { value: 2027, text: '2027' },
                    { value: 2026, text: '2026' },
                    { value: 2025, text: '2025' },
                    { value: 2024, text: '2024' },
                    { value: 2023, text: '2023' },
                    { value: 2022, text: '2022' },
                    { value: 2021, text: '2021' },
                    { value: 2020, text: '2020' },  
                    { value: 2019, text: '2019' },
                    { value: 2018, text: '2018' },
                    { value: 2017, text: '2017' },
                    { value: 2016, text: '2016' },
                    { value: 2015, text: '2015' },
                    { value: 2014, text: '2014' },
                    { value: 2013, text: '2013' },  
                    { value: 2012, text: '2012' },
                    { value: 2011, text: '2011' },
                    { value: 2010, text: '2010' },
                    { value: 2009, text: '2009' },
                    { value: 2008, text: '2008' },
                    { value: 2007, text: '2007' },
                    { value: 2006, text: '2006' },
                    { value: 2005, text: '2005' },
                    { value: 2004, text: '2004' },
                    { value: 2003, text: '2003' },
                    { value: 2002, text: '2002' },
                    { value: 2001, text: '2001' },
                    { value: 2000, text: '2000' },
                    { value: 1999, text: '1999' },
                    { value: 1998, text: '1998' },
                    { value: 1997, text: '1997' },
                    { value: 1996, text: '1996' },
                    { value: 1995, text: '1995' },
                    { value: 1994, text: '1994' },
                    { value: 1993, text: '1993' },
                    { value: 1992, text: '1992' }
                ]
                //DOM.emailGalleryYearFilter.innerHTML = '<option value="0" selected>All Years</option>';
                years.forEach(year => {
                    const option = document.createElement('option');
                    option.value = year.value;
                    option.textContent = year.text;
                    DOM.emailGalleryYearFilter.appendChild(option);
                });

                // Setup month filter
                const months = [
                    { value: 0, text: 'All Months' },
                    { value: 1, text: 'January' },
                    { value: 2, text: 'February' },
                    { value: 3, text: 'March' },
                    { value: 4, text: 'April' },
                    { value: 5, text: 'May' },
                    { value: 6, text: 'June' },
                    { value: 7, text: 'July' },
                    { value: 8, text: 'August' },
                    { value: 9, text: 'September' },
                    { value: 10, text: 'October' },
                    { value: 11, text: 'November' },
                    { value: 12, text: 'December' }
                ];
                DOM.emailGalleryMonthFilter.innerHTML = '';
                months.forEach(month => {
                    const option = document.createElement('option');
                    option.value = month.value;
                    option.textContent = month.text;
                    DOM.emailGalleryMonthFilter.appendChild(option);
                });

                // Setup folder filter
                // const folders = [...new Set(emailData.map(email => email.metadata.source_file))].sort();
                // DOM.emailGalleryFolderFilter.innerHTML = '<option value="all" selected>All Folders</option>';
                // folders.forEach(folder => {
                //     const option = document.createElement('option');
                //     option.value = folder;
                //     option.textContent = folder;
                //     DOM.emailGalleryFolderFilter.appendChild(option);
                // });
            }

            function _handleSearch() {
                const searchTerm = DOM.emailGallerySearch.value.trim();
                const senderFilter = DOM.emailGallerySender.value.trim();
                const recipientFilter = DOM.emailGalleryRecipient.value.trim();
                const toFromFilter = DOM.emailGalleryToFrom.value.trim();
                const yearFilter = DOM.emailGalleryYearFilter.value;
                const monthFilter = DOM.emailGalleryMonthFilter.value;
                const businessFilter = DOM.emailGalleryBusinessFilter.checked;
                const attachmentsFilter = DOM.emailGalleryAttachmentsFilter.checked;
                //const folderFilter = DOM.emailGalleryFolderFilter.value;

                // Build query parameters for /emails/search endpoint
                const params = new URLSearchParams();
                
                if (searchTerm) {
                    params.append('subject', searchTerm);
                }
                if (senderFilter) {
                    params.append('from_address', senderFilter);
                }
                if (recipientFilter) {
                    params.append('to_address', recipientFilter);
                }
                if (toFromFilter) {
                    params.append('to_from', toFromFilter);
                }
                if (yearFilter && yearFilter !== '0' && yearFilter !== '') {
                    params.append('year', yearFilter);
                }
                if (monthFilter && monthFilter !== '0' && monthFilter !== '') {
                    params.append('month', monthFilter);
                }
                if (attachmentsFilter) {
                    params.append('has_attachments', 'true');
                }
                // Note: business filter is not supported by the new endpoint

                // Reset pagination for new search
                currentPage = 0;
                hasMoreData = true;
                
                fetch('/emails/search?' + params.toString())
                .then(r => r.json())
                .then(data => {
                    // Transform response to match expected format
                
                    emailData = data.map(email => ({
                        id: email.id,
                        subject: email.subject || 'No Subject',
                        sender: email.from_address || 'Unknown Sender',
                        recipient: email.to_addresses || 'Unknown Recipient',
                        date: email.date ? formatDateAustralian(email.date) : 'No Date',
                        folder: email.folder || 'Unknown Folder',
                        body: email.snippet || 'No content',
                        preview: email.snippet || 'No preview',
                        attachments: email.attachment_ids.map(id => `/attachments/${id}`),
                        emailId: email.id // Store email ID for fetching full content
                    }));
                    selectedEmailIndex = -1;
                    _renderEmailList();
                    _showInstructions();
                    _updateEmailDetails();
                    _selectFirstEmail();
             })
             .catch(error => {
                 console.error('Error searching emails:', error);
                 emailData = [];
                 _renderEmailList();
                 _showInstructions();
             });
            }

            function _selectFirstEmail() {
                if (emailData.length > 0) {
                    _selectEmail(0);
                }
            }

            function _handleClear() {
                DOM.emailGallerySearch.value = '';
                DOM.emailGallerySender.value = '';
                DOM.emailGalleryRecipient.value = '';
                DOM.emailGalleryToFrom.value = '';
                DOM.emailGalleryYearFilter.value = 0;
                DOM.emailGalleryMonthFilter.value = 0;
                DOM.emailGalleryBusinessFilter.checked = false;
                DOM.emailGalleryAttachmentsFilter.checked = false;
                DOM.emailGalleryList.innerHTML = '';
                DOM.emailGalleryEmailContent.style.display = 'none';
                DOM.emailGalleryEmailDetails.style.display = 'none';
                //DOM.emailGalleryFolderFilter.value = 'all';
                
                // Reset pagination for clear
                currentPage = 0;
                hasMoreData = true;
                //_handleSearch();
            }

            function _handleAttachmentsFilter() {
                // Trigger new search with attachments filter
                _handleSearch();
            }

            function _renderEmailList() {
                // Reset pagination when rendering new list
                currentPage = 0;
                hasMoreData = true;
                DOM.emailGalleryList.innerHTML = '';

                if (emailData.length === 0) {
                    const noResults = document.createElement('div');
                    noResults.style.textAlign = 'center';
                    noResults.style.padding = '2em';
                    noResults.style.color = '#666';
                    noResults.textContent = 'No emails found matching your criteria';
                    DOM.emailGalleryList.appendChild(noResults);
                    return;
                }

                _loadMoreEmails();
            }

            function _loadMoreEmails() {
                if (isLoading || !hasMoreData) return;

                isLoading = true;
                
                // Note: Attachments filter is now handled server-side via has_attachments parameter
                const startIndex = currentPage * itemsPerPage;
                const endIndex = startIndex + itemsPerPage;
                const emailsToRender = emailData.slice(startIndex, endIndex);

                if (emailsToRender.length === 0) {
                    hasMoreData = false;
                    isLoading = false;
                    return;
                }

                emailsToRender.forEach((email, localIndex) => {
                 
                    const actualIndex = startIndex + localIndex;
                    const emailItem = document.createElement('div');
                    emailItem.className = 'email-list-item';
                    emailItem.dataset.index = actualIndex;

                    // Add has-attachments class if email has attachments
                    if (email.attachments && email.attachments.length > 0) {
                        emailItem.classList.add('has-attachments');
                    }

                    emailItem.innerHTML = `
                        <div class="email-subject">${email.subject || 'No Subject'}</div>
                        <div class="email-sender">From: ${email.sender || 'Unknown Sender'}</div>
                        <div class="email-date">${email.date || 'No Date'}</div>
                        <div class="email-preview">${email.preview || 'No Preview'}</div>
                    `;

                    emailItem.addEventListener('click', () => _selectEmail(actualIndex));
                    DOM.emailGalleryList.appendChild(emailItem);
                });

                currentPage++;
                hasMoreData = endIndex < emailData.length;
                isLoading = false;

                // Add loading indicator if there's more data
                if (hasMoreData) {
                    _addLoadingIndicator();
                }
            }

            function _addLoadingIndicator() {
                // Remove existing loading indicator
                const existingIndicator = DOM.emailGalleryList.querySelector('.loading-indicator');
                if (existingIndicator) {
                    existingIndicator.remove();
                }

                const loadingIndicator = document.createElement('div');
                loadingIndicator.className = 'loading-indicator';
                loadingIndicator.innerHTML = `
                    <div style="text-align: center; padding: 1em; color: #666;">
                        <div style="display: inline-block; width: 20px; height: 20px; border: 2px solid #f3f3f3; border-top: 2px solid #4a90e2; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                        <div style="margin-top: 0.5em;">Loading more emails...</div>
                    </div>
                `;
                DOM.emailGalleryList.appendChild(loadingIndicator);
            }

            function _handleEmailListScroll() {
                const { scrollTop, scrollHeight, clientHeight } = DOM.emailGalleryList;
                
                // Load more emails when user scrolls to within 100px of the bottom
                if (scrollTop + clientHeight >= scrollHeight - 100) {
                    _loadMoreEmails();
                }
            }

            function _selectEmail(index) {
                selectedEmailIndex = index;
                
                // Update visual selection using dataset.index to match actual emailData index
                document.querySelectorAll('.email-list-item').forEach((item) => {
                    const itemIndex = parseInt(item.dataset.index, 10);
                    item.classList.toggle('selected', itemIndex === index);
                });

                // Display email directly (filtering is now handled server-side)
                if (emailData[index]) {
                    _displayEmail(emailData[index]);
                } else {
                    console.error(`Email at index ${index} not found in emailData`);
                }
                _updateEmailDetails();
            }

            function _displayEmail(email) {
               
               // const emailDate = new Date(email.date);
               // const formattedDate = emailDate.toLocaleDateString() + ' ' + emailDate.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});

                // Update email content with metadata
                DOM.emailGalleryEmailContent.querySelector('.email-metadata .email-subject').textContent = email.subject || 'No Subject';
                DOM.emailGalleryEmailContent.querySelector('.email-metadata .email-from').textContent = email.sender || 'Unknown Sender';
                DOM.emailGalleryEmailContent.querySelector('.email-metadata .email-date').textContent = email.date || 'No Date';
                DOM.emailGalleryEmailContent.querySelector('.email-metadata .email-folder').textContent = email.folder || 'Unknown Folder';
                
                // Show loading for email body
                const emailBodyElement = DOM.emailGalleryEmailContent.querySelector('.email-body');
                emailBodyElement.innerHTML = '<div style="text-align: center; padding: 20px; color: #666;">Loading email content...</div>';
                
                // Fetch full email content if emailId is available
                if (email.emailId) {
                    fetch(`/emails/${email.emailId}/html`)
                        .then(response => {
                            if (response.ok) {
                                return response.text();
                            } else {
                                // Fallback to plain text
                                return fetch(`/emails/${email.emailId}/text`)
                                    .then(r => {
                                        if (r.ok) {
                                            return r.text();
                                        } else {
                                            throw new Error('Failed to fetch email content');
                                        }
                                    });
                            }
                        })
                        .then(content => {
                            // Clear the loading message
                            emailBodyElement.innerHTML = '';
                            
                            let htmlContent = content;
                            
                            // If content is plain text, wrap it in HTML document structure
                            if (!content.trim().startsWith('<!DOCTYPE') && !content.trim().startsWith('<html')) {
                                htmlContent = `<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 20px auto;
            padding: 20px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
    </style>
</head>
<body>
${content}
</body>
</html>`;
                            }
                            
                            // Create an iframe to display the HTML email content
                            const iframe = document.createElement('iframe');
                            iframe.srcdoc = htmlContent;
                            iframe.style.width = '100%';
                            iframe.style.minHeight = '600px';
                            iframe.style.border = 'none';
                            iframe.style.borderRadius = '6px';
                            emailBodyElement.appendChild(iframe);
                        })
                        .catch(error => {
                            console.error('Error fetching email content:', error);
                            emailBodyElement.innerHTML = `<div style="color: #c33; padding: 20px; text-align: center;">Error loading email: ${error.message}</div>`;
                        });
                } else {
                    emailBodyElement.innerHTML = '<div style="padding: 20px; color: #666;">No content available</div>';
                }

                DOM.emailGalleryEmailContent.querySelector('.email-attachments').innerHTML = '';
                if (email.attachments && email.attachments.length > 0) {
                    debugger;
                        email.attachments.forEach(attachment => {
                        const attachmentItem = document.createElement('img');
                        attachmentItem.className = 'email-attachment';
                        // Add query parameters for preview
                        attachmentItem.src = attachment + "?preview=true&resize_to=100";
                        attachmentItem.style.maxWidth = '100px';
                        attachmentItem.style.objectFit = 'cover';
                        attachmentItem.style.cursor = 'pointer';
                        attachmentItem.addEventListener('click', () => _attachmentsViewer(email.attachments,  attachment));
                        DOM.emailGalleryEmailContent.querySelector('.email-attachments').appendChild(attachmentItem);
                    });
                }

                // Show email content, hide instructions
                DOM.emailGalleryInstructions.style.display = 'none';
                DOM.emailGalleryEmailContent.style.display = 'block';
            }

            function _attachmentsViewer(emailAttachments, selectedAttachment){
                // Extract attachment ID from URL (e.g., "/attachments/123" -> "123")
                const getAttachmentId = (url) => {
                    const match = url.match(/\/attachments\/(\d+)/);
                    return match ? match[1] : null;
                };

                // Extract filename from URL or use default
                const getFilename = (url) => {
                    const id = getAttachmentId(url);
                    return id ? `Attachment ${id}` : 'Attachment';
                };

                if (emailAttachments.length > 1) {
                    // Show the attachments in a carousel with the selected attachment in the center
                    // Remove query parameters from selectedAttachment for matching
                    const cleanSelectedAttachment = selectedAttachment.split('?')[0];
                    Modals.MultiImageDisplay.showMultiImageModal(emailAttachments, cleanSelectedAttachment);
                } else {
                    // Show the attachment in a modal
                    const attachmentUrl = emailAttachments[0].split('?')[0]; // Remove query params
                    const filename = getFilename(attachmentUrl);
                    Modals.SingleImageDisplay.showSingleImageModal(filename, attachmentUrl, 0, 0, 0);
                }
            }

            function _showInstructions() {
                DOM.emailGalleryInstructions.style.display = 'flex';
                DOM.emailGalleryEmailContent.style.display = 'none';
            }

            function _clearEmailContent() {
                DOM.emailGalleryEmailContent.querySelector('.email-subject').textContent = '';
                DOM.emailGalleryEmailContent.querySelector('.email-from').textContent = '';
                DOM.emailGalleryEmailContent.querySelector('.email-to').textContent = '';
                DOM.emailGalleryEmailContent.querySelector('.email-date').textContent = '';
                DOM.emailGalleryEmailContent.querySelector('.email-folder').textContent = '';
                DOM.emailGalleryEmailContent.querySelector('.email-body').textContent = '';
            }

            function _updateEmailDetails() {
                let filteredEmails = emailData;
                if (DOM.emailGalleryAttachmentsFilter.checked) {
                    filteredEmails = emailData.filter(email => 
                        email.attachments && email.attachments.length > 0
                    );
                }
                
                //const count = filteredEmails.length;
                //const total = emailData.length;
                //DOM.emailGalleryEmailDetails.textContent = `Showing ${count} of ${total} emails`;
            }

            function _handleKeydown(event) {
                if (DOM.emailGalleryModal.style.display !== 'flex') return;
                

                switch(event.key) {
                    case 'Escape':
                        close();
                        break;
                    case 'ArrowDown':
                        event.preventDefault();
                        if (selectedEmailIndex < emailData.length - 1) {
                            _selectEmail(selectedEmailIndex + 1);
                            _scrollToSelectedEmail();
                        }
                        break;
                    case 'ArrowUp':
                        event.preventDefault();
                        if (selectedEmailIndex > 0) {
                            _selectEmail(selectedEmailIndex - 1);
                            _scrollToSelectedEmail();
                        }
                        break;
                }
            }

            function openContact(contactName) {
                DOM.emailGalleryToFrom.value = contactName;
                DOM.emailGalleryModal.style.display = 'flex';
                //_loadEmailData();
                _handleSearch();
            }

            function _scrollToSelectedEmail() {
                const selectedItem = document.querySelector('.email-list-item.selected');
                if (selectedItem) {
                    selectedItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            }

            return { init, open, close, openContact };
        })(),

        ConfirmationModal: (() => {

            let onConfirm = () => {
                DOM.confirmationModal.style.display = 'none';
            }

            function init() {

                DOM.confirmationModalCancelBtn.addEventListener('click', () => DOM.confirmationModal.style.display = 'none');
                DOM.confirmationModalCloseBtn.addEventListener('click', () => DOM.confirmationModal.style.display = 'none');
                DOM.confirmationModalConfirmBtn.addEventListener('click',() => _handleConfirm());

            }
            function open(title, text, onConfirmFn) {
                DOM.confirmationModal.style.display = 'flex';
                DOM.confirmationModalTitle.textContent = title;
                DOM.confirmationModalText.textContent = text;

                onConfirm = onConfirmFn;

            }

            function _handleConfirm() {
                _closeConfirmationModal();
                if (typeof onConfirm === 'function') {
                    onConfirm();
                }
            }


            const _closeConfirmationModal = () => {
                DOM.confirmationModal.style.display = 'none';
            }

            return { init,open };
        })(),

        SMSMessages: (() => {
            let chatSessions = [];
            let filteredSessions = [];
            let originalChatData = null;
            let currentSession = null;
            let messageTypeFilters = {
                imessage: true,
                sms: true,
                whatsapp: true,
                mixed: true
            };

            function formatAustralianDate(dateString) {
                if (!dateString) return '';
                const date = new Date(dateString);
                const day = String(date.getDate()).padStart(2, '0');
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const year = date.getFullYear();
                const hours = String(date.getHours()).padStart(2, '0');
                const minutes = String(date.getMinutes()).padStart(2, '0');
                const seconds = String(date.getSeconds()).padStart(2, '0');
                return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
            }

            async function loadChatSessions() {
                const listContainer = document.getElementById('sms-chat-sessions-list');
                if (!listContainer) return;

                listContainer.innerHTML = '<div style="text-align: center; padding: 2rem; color: #666;">Loading conversations...</div>';

                try {
                    const response = await fetch('/imessages/chat-sessions');
                    if (!response.ok) {
                        throw new Error('Failed to load chat sessions');
                    }
                    const data = await response.json();
                    // Store original data structure
                    originalChatData = data;
                    // Combine both categories for filtering
                    chatSessions = [
                        ...(data.contacts_and_groups || []),
                        ...(data.other || [])
                    ];
                    filteredSessions = [...chatSessions];
                    renderChatSessions();
                } catch (error) {
                    console.error('Error loading chat sessions:', error);
                    let errorMessage = 'Error loading conversations';
                    if (error.message) {
                        errorMessage += ': ' + error.message;
                    }
                    listContainer.innerHTML = `<div style="text-align: center; padding: 2rem; color: #dc3545;">${errorMessage}</div>`;
                }
            }

            function renderChatSessions() {
                const listContainer = document.getElementById('sms-chat-sessions-list');
                if (!listContainer) return;

                // First filter by message type
                const typeFilteredSessions = filteredSessions.filter(session => {
                    return messageTypeFilters[session.message_type] === true;
                });

                // Get data from API response structure
                const contactsAndGroups = typeFilteredSessions.filter(session => {
                    // Check if it's a phone number (same logic as backend)
                    const chatSession = session.chat_session || '';
                    const cleaned = chatSession.replace(/[\s\-\(\)]/g, '');
                    if (cleaned.startsWith('+')) {
                        return !cleaned.substring(1).match(/^\d{7,}$/);
                    }
                    const digitCount = (chatSession.match(/\d/g) || []).length;
                    return !(digitCount >= 7 && cleaned.length <= 20);
                });
                
                const otherSessions = typeFilteredSessions.filter(session => {
                    const chatSession = session.chat_session || '';
                    const cleaned = chatSession.replace(/[\s\-\(\)]/g, '');
                    if (cleaned.startsWith('+')) {
                        return cleaned.substring(1).match(/^\d{7,}$/);
                    }
                    const digitCount = (chatSession.match(/\d/g) || []).length;
                    return digitCount >= 7 && cleaned.length <= 20;
                });

                if (typeFilteredSessions.length === 0) {
                    listContainer.innerHTML = '<div style="text-align: center; padding: 2rem; color: #666;">No conversations found</div>';
                    return;
                }

                listContainer.innerHTML = '';
                
                // Render Contacts and Groups section
                if (contactsAndGroups.length > 0) {
                    const categoryHeader = document.createElement('div');
                    categoryHeader.className = 'sms-chat-category-header';
                    categoryHeader.textContent = 'Contacts and Groups';
                    categoryHeader.style.cssText = 'padding: 12px 16px; font-weight: 600; font-size: 13px; color: #233366; background-color: #e9ecef; border-bottom: 1px solid #dee2e6; text-transform: uppercase; letter-spacing: 0.5px;';
                    listContainer.appendChild(categoryHeader);
                    
                    contactsAndGroups.forEach(session => {
                        renderChatSessionItem(session, listContainer);
                    });
                }
                
                // Render Other section
                if (otherSessions.length > 0) {
                    const categoryHeader = document.createElement('div');
                    categoryHeader.className = 'sms-chat-category-header';
                    categoryHeader.textContent = 'Other';
                    categoryHeader.style.cssText = 'padding: 12px 16px; font-weight: 600; font-size: 13px; color: #233366; background-color: #e9ecef; border-bottom: 1px solid #dee2e6; border-top: 1px solid #dee2e6; margin-top: ' + (contactsAndGroups.length > 0 ? '8px' : '0') + '; text-transform: uppercase; letter-spacing: 0.5px;';
                    listContainer.appendChild(categoryHeader);
                    
                    otherSessions.forEach(session => {
                        renderChatSessionItem(session, listContainer);
                    });
                }
            }

            function renderChatSessionItem(session, listContainer) {
                    const item = document.createElement('div');
                    item.className = 'sms-chat-session-item';
                    item.dataset.session = session.chat_session;
                    
                    const nameSpan = document.createElement('span');
                    nameSpan.className = 'sms-chat-session-name';
                    
                    // Message type icon (SMS or iMessage)
                    const messageTypeIcon = document.createElement('i');
                    if (session.message_type === 'imessage') {
                        messageTypeIcon.className = 'fab fa-apple';
                        messageTypeIcon.title = 'iMessage';
                        messageTypeIcon.style.marginRight = '6px';
                        messageTypeIcon.style.color = '#007AFF';
                    } else if (session.message_type === 'sms') {
                        messageTypeIcon.className = 'fas fa-comment';
                        messageTypeIcon.title = 'SMS';
                        messageTypeIcon.style.marginRight = '6px';
                        messageTypeIcon.style.color = '#34C759';
                    } else if (session.message_type === 'whatsapp') {
                        messageTypeIcon.className = 'fab fa-whatsapp';
                        messageTypeIcon.title = 'WhatsApp';
                        messageTypeIcon.style.marginRight = '6px';
                        messageTypeIcon.style.color = '#25D366';
                    } else if (session.message_type === 'mixed') {
                        messageTypeIcon.className = 'fas fa-comments';
                        messageTypeIcon.title = 'Mixed (SMS, iMessage & WhatsApp)';
                        messageTypeIcon.style.marginRight = '6px';
                        messageTypeIcon.style.color = '#FF9500';
                    }
                    nameSpan.appendChild(messageTypeIcon);
                    
                    const nameText = document.createTextNode(session.chat_session || 'Unknown');
                    nameSpan.appendChild(nameText);
                    
                    // Attachment indicator
                    if (session.has_attachments) {
                        const attachmentIcon = document.createElement('i');
                        attachmentIcon.className = 'fas fa-paperclip';
                        attachmentIcon.style.marginLeft = '8px';
                        attachmentIcon.style.color = '#666';
                        attachmentIcon.style.fontSize = '12px';
                        attachmentIcon.title = `${session.attachment_count || 0} attachment(s)`;
                        nameSpan.appendChild(attachmentIcon);
                    }
                    
                    const countSpan = document.createElement('span');
                    countSpan.className = 'sms-chat-session-count';
                    countSpan.textContent = session.message_count || 0;
                    
                    item.appendChild(nameSpan);
                    item.appendChild(countSpan);
                    
                    item.addEventListener('click', () => selectChatSession(session.chat_session));
                    
                    listContainer.appendChild(item);
            }

            async function selectChatSession(sessionName) {
                // Update active state
                const items = document.querySelectorAll('.sms-chat-session-item');
                items.forEach(item => {
                    if (item.dataset.session === sessionName) {
                        item.classList.add('active');
                    } else {
                        item.classList.remove('active');
                    }
                });

                currentSession = sessionName;
                
                // Find the selected session to get its message_type
                const selectedSession = chatSessions.find(s => s.chat_session === sessionName);
                const messageType = selectedSession?.message_type || 'sms';
                
                const titleElement = document.getElementById('sms-conversation-title-text');
                const typeIconElement = document.getElementById('sms-conversation-type-icon');
                const deleteBtn = document.getElementById('sms-delete-conversation-btn');
                const askAIBtn = document.getElementById('sms-ask-ai-btn');
                
                if (titleElement) {
                    titleElement.textContent = sessionName || 'Unknown Conversation';
                }
                
                // Update conversation type icon
                if (typeIconElement) {
                    typeIconElement.innerHTML = ''; // Clear previous icon
                    typeIconElement.style.display = sessionName ? 'inline-block' : 'none';
                    
                    if (sessionName) {
                        const icon = document.createElement('i');
                        if (messageType === 'imessage') {
                            icon.className = 'fab fa-apple';
                            icon.title = 'iMessage';
                            icon.style.color = '#007AFF';
                        } else if (messageType === 'sms') {
                            icon.className = 'fas fa-comment';
                            icon.title = 'SMS';
                            icon.style.color = '#34C759';
                        } else if (messageType === 'whatsapp') {
                            icon.className = 'fab fa-whatsapp';
                            icon.title = 'WhatsApp';
                            icon.style.color = '#25D366';
                        } else if (messageType === 'mixed') {
                            icon.className = 'fas fa-comments';
                            icon.title = 'Mixed (SMS, iMessage & WhatsApp)';
                            icon.style.color = '#FF9500';
                        }
                        typeIconElement.appendChild(icon);
                    }
                }
                
                if (deleteBtn) {
                    deleteBtn.style.display = sessionName ? 'block' : 'none';
                }
                
                if (askAIBtn) {
                    askAIBtn.style.display = sessionName ? 'block' : 'none';
                }

                const messagesContainer = document.getElementById('sms-conversation-messages');
                const instructionsElement = document.getElementById('sms-conversation-instructions');
                
                if (instructionsElement) {
                    instructionsElement.style.display = 'none';
                }

                if (!messagesContainer) return;

                messagesContainer.innerHTML = '<div style="text-align: center; padding: 2rem; color: #666;">Loading messages...</div>';

                try {
                    const encodedSession = encodeURIComponent(sessionName);
                    const response = await fetch(`/imessages/conversation/${encodedSession}`);
                    if (!response.ok) {
                        throw new Error('Failed to load messages');
                    }
                    const data = await response.json();
                    displayMessages(data.messages || []);
                } catch (error) {
                    console.error('Error loading messages:', error);
                    messagesContainer.innerHTML = '<div style="text-align: center; padding: 2rem; color: #dc3545;">Error loading messages</div>';
                }
            }

            function displayMessages(messages) {
                const messagesContainer = document.getElementById('sms-conversation-messages');
                if (!messagesContainer) return;

                messagesContainer.innerHTML = '';

                messages.forEach(message => {
                    const messageDiv = document.createElement('div');
                    const isIncoming = message.type === 'Incoming';
                    messageDiv.className = `sms-message ${isIncoming ? 'incoming' : 'outgoing'}`;

                    const bubble = document.createElement('div');
                    bubble.className = 'sms-message-bubble';

                    // Header with sender and date
                    const header = document.createElement('div');
                    header.className = 'sms-message-header';
                    
                    const senderSpan = document.createElement('span');
                    senderSpan.className = 'sms-message-sender';
                    senderSpan.textContent = message.sender_name || message.sender_id || (isIncoming ? 'Incoming' : 'Outgoing');
                    
                    const dateSpan = document.createElement('span');
                    dateSpan.className = 'sms-message-date';
                    dateSpan.textContent = formatAustralianDate(message.message_date);
                    
                    header.appendChild(senderSpan);
                    header.appendChild(dateSpan);
                    bubble.appendChild(header);

                    // Message text
                    if (message.text) {
                        const textDiv = document.createElement('div');
                        textDiv.className = 'sms-message-text';
                        textDiv.textContent = message.text;
                        bubble.appendChild(textDiv);
                    }

                    // Attachment
                    if (message.has_attachment && message.attachment_filename) {
                        const attachmentDiv = document.createElement('div');
                        attachmentDiv.className = 'sms-message-attachment';
                        
                        const img = document.createElement('img');
                        img.src = `/imessages/${message.id}/attachment`;
                        img.alt = message.attachment_filename;
                        img.style.maxWidth = '200px';
                        img.style.maxHeight = '200px';
                        img.style.objectFit = 'contain';
                        
                        img.onerror = function() {
                            // If image fails to load, show filename
                            attachmentDiv.innerHTML = `<div style="padding: 8px; background-color: rgba(0,0,0,0.1); border-radius: 4px; font-size: 12px;">${message.attachment_filename}</div>`;
                        };
                        
                        img.addEventListener('click', () => {
                            showFullAttachment(message.id, message.attachment_filename, message.attachment_type);
                        });
                        
                        attachmentDiv.appendChild(img);
                        bubble.appendChild(attachmentDiv);
                    }

                    messageDiv.appendChild(bubble);
                    messagesContainer.appendChild(messageDiv);
                });

                // Scroll to bottom
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }

            function showFullAttachment(messageId, filename, contentType) {
                // Use existing single image modal
                const modal = document.getElementById('single-image-modal');
                const modalImg = document.getElementById('single-image-modal-img');
                const modalVideo = document.getElementById('single-image-modal-video');
                const modalAudio = document.getElementById('single-image-modal-audio');
                const modalPdf = document.getElementById('single-image-modal-pdf');
                const modalDetails = document.getElementById('single-image-details');

                if (!modal) return;

                // Hide all media elements
                modalImg.style.display = 'none';
                modalVideo.style.display = 'none';
                modalAudio.style.display = 'none';
                modalPdf.style.display = 'none';

                const attachmentUrl = `/imessages/${messageId}/attachment`;
                const isImage = contentType && contentType.startsWith('image/');
                const isVideo = contentType && contentType.startsWith('video/');
                const isAudio = contentType && contentType.startsWith('audio/');
                const isPdf = contentType === 'application/pdf';

                if (modalDetails) {
                    modalDetails.textContent = filename || 'Attachment';
                }

                if (isImage) {
                    modalImg.src = attachmentUrl;
                    modalImg.style.display = 'block';
                } else if (isVideo) {
                    modalVideo.src = attachmentUrl;
                    modalVideo.style.display = 'block';
                } else if (isAudio) {
                    modalAudio.src = attachmentUrl;
                    modalAudio.style.display = 'block';
                } else if (isPdf) {
                    modalPdf.src = attachmentUrl;
                    modalPdf.style.display = 'block';
                } else {
                    // For other file types, try to show as image first
                    modalImg.src = attachmentUrl;
                    modalImg.style.display = 'block';
                    modalImg.onerror = function() {
                        // If it fails, show download link
                        modalImg.style.display = 'none';
                        if (modalDetails) {
                            modalDetails.innerHTML = `<div style="padding: 20px; text-align: center;">
                                <p>${filename || 'Attachment'}</p>
                                <a href="${attachmentUrl}" download style="color: #4a90e2; text-decoration: underline;">Download</a>
                            </div>`;
                        }
                    };
                }

                modal.style.display = 'flex';
            }

            function searchChatSessions(query) {
                const searchTerm = query.toLowerCase().trim();
                if (!searchTerm) {
                    filteredSessions = [...chatSessions];
                } else {
                    filteredSessions = chatSessions.filter(session => 
                        session.chat_session && session.chat_session.toLowerCase().includes(searchTerm)
                    );
                }
                renderChatSessions();
            }

            async function deleteConversation() {
                if (!currentSession) return;

                // Show confirmation dialog
                const confirmed = confirm(`Are you sure you want to delete the conversation "${currentSession}"?\n\nThis action cannot be undone.`);
                if (!confirmed) {
                    return;
                }

                try {
                    const encodedSession = encodeURIComponent(currentSession);
                    const response = await fetch(`/imessages/conversation/${encodedSession}`, {
                        method: 'DELETE'
                    });

                    if (!response.ok) {
                        const error = await response.json();
                        throw new Error(error.detail || 'Failed to delete conversation');
                    }

                    const result = await response.json();
                    
                    // Clear the conversation view
                    currentSession = null;
                    const titleElement = document.getElementById('sms-conversation-title');
                    const deleteBtn = document.getElementById('sms-delete-conversation-btn');
                    const messagesContainer = document.getElementById('sms-conversation-messages');
                    const instructionsElement = document.getElementById('sms-conversation-instructions');
                    
                    if (titleElement) {
                        titleElement.textContent = 'Select a conversation';
                    }
                    if (deleteBtn) {
                        deleteBtn.style.display = 'none';
                    }
                    if (messagesContainer) {
                        messagesContainer.innerHTML = '';
                    }
                    if (instructionsElement) {
                        instructionsElement.style.display = 'block';
                    }

                    // Remove active state from all items
                    const items = document.querySelectorAll('.sms-chat-session-item');
                    items.forEach(item => item.classList.remove('active'));

                    // Reload chat sessions list
                    await loadChatSessions();
                    
                    alert(`Successfully deleted ${result.deleted_count} message(s) from the conversation.`);
                } catch (error) {
                    console.error('Error deleting conversation:', error);
                    alert(`Error deleting conversation: ${error.message}`);
                }
            }

            function init() {
                const searchInput = document.getElementById('sms-chat-search');
                if (searchInput) {
                    searchInput.addEventListener('input', (e) => {
                        searchChatSessions(e.target.value);
                    });
                }

                // Add event listeners for message type filter checkboxes
                const filterCheckboxes = {
                    'filter-imessage': 'imessage',
                    'filter-sms': 'sms',
                    'filter-whatsapp': 'whatsapp',
                    'filter-mixed': 'mixed'
                };

                Object.keys(filterCheckboxes).forEach(checkboxId => {
                    const checkbox = document.getElementById(checkboxId);
                    if (checkbox) {
                        checkbox.addEventListener('change', (e) => {
                            messageTypeFilters[filterCheckboxes[checkboxId]] = e.target.checked;
                            renderChatSessions();
                        });
                    }
                });

                const deleteBtn = document.getElementById('sms-delete-conversation-btn');
                if (deleteBtn) {
                    deleteBtn.addEventListener('click', (e) => {
                        e.stopPropagation(); // Prevent any event bubbling
                        deleteConversation();
                    });
                }

                // Ask AI button and modal handlers
                const askAIBtn = document.getElementById('sms-ask-ai-btn');
                const askAIModal = document.getElementById('sms-ask-ai-modal');
                const askAICloseBtn = document.getElementById('sms-ask-ai-close');
                const askAICancelBtn = document.getElementById('sms-ask-ai-cancel');
                const askAISubmitBtn = document.getElementById('sms-ask-ai-submit');
                const askAIRadioButtons = document.querySelectorAll('input[name="sms-ask-ai-option"]');
                const askAIOtherTextarea = document.getElementById('sms-ask-ai-other-text');
                const askAIOtherInput = document.getElementById('sms-ask-ai-other-input');

                if (askAIBtn && askAIModal) {
                    askAIBtn.addEventListener('click', () => {
                        // Update conversation title in modal
                        const conversationTitleEl = document.getElementById('sms-ask-ai-conversation-title');
                        const conversationTitle = document.getElementById('sms-conversation-title');
                        if (conversationTitleEl && conversationTitle) {
                            conversationTitleEl.textContent = conversationTitle.textContent || 'Unknown Conversation';
                        }
                        askAIModal.style.display = 'flex';
                    });
                }

                if (askAICloseBtn && askAIModal) {
                    askAICloseBtn.addEventListener('click', () => {
                        askAIModal.style.display = 'none';
                    });
                }

                if (askAICancelBtn && askAIModal) {
                    askAICancelBtn.addEventListener('click', () => {
                        askAIModal.style.display = 'none';
                    });
                }

                if (askAISubmitBtn) {
                    askAISubmitBtn.addEventListener('click', () => {
                        // Functionality will be added later
                        const selectedOption = document.querySelector('input[name="sms-ask-ai-option"]:checked')?.value;
                        const otherText = askAIOtherInput?.value || '';
                        console.log('Ask AI - Selected option:', selectedOption, 'Other text:', otherText);
                        // TODO: Implement AI functionality
                        askAIModal.style.display = 'none';
                    });
                }

                // Toggle textarea visibility based on radio selection
                if (askAIRadioButtons.length > 0 && askAIOtherTextarea) {
                    askAIRadioButtons.forEach(radio => {
                        radio.addEventListener('change', () => {
                            if (radio.value === 'other') {
                                askAIOtherTextarea.style.display = 'block';
                            } else {
                                askAIOtherTextarea.style.display = 'none';
                            }
                        });
                    });
                }

                // Close modal when clicking outside
                if (askAIModal) {
                    askAIModal.addEventListener('click', (e) => {
                        if (e.target === askAIModal) {
                            askAIModal.style.display = 'none';
                        }
                    });
                }

                const closeBtn = document.getElementById('close-sms-messages-modal');
                if (closeBtn) {
                    closeBtn.addEventListener('click', () => {
                        const modal = document.getElementById('sms-messages-modal');
                        if (modal) {
                            modal.style.display = 'none';
                        }
                    });
                }

                const modal = document.getElementById('sms-messages-modal');
                if (modal) {
                    modal.addEventListener('click', (e) => {
                        if (e.target === modal) {
                            modal.style.display = 'none';
                        }
                    });
                }
            }

            function open() {
                const modal = document.getElementById('sms-messages-modal');
                if (modal) {
                    modal.style.display = 'flex';
                    loadChatSessions();
                }
            }

            return { init, open };
        })(),

        ChangeUserId: (() => {
            function init() {
                // Show modal when button is clicked
                if (DOM.changeUserIdBtn) {
                    DOM.changeUserIdBtn.addEventListener('click', function() {
                        // Get current user ID from localStorage or set default
                        const currentUserId = localStorage.getItem('userId') || 'default';
                        DOM.currentUserIdInput.value = currentUserId;
                        DOM.newUserIdInput.value = '';
                        DOM.changeUserIdModal.style.display = 'flex';
                    });
                }

                // Close modal functions
                function closeChangeUserIdModalFunc() {
                    DOM.changeUserIdModal.style.display = 'none';
                }

                if (DOM.closeChangeUserIdModalBtn) {
                    DOM.closeChangeUserIdModalBtn.addEventListener('click', closeChangeUserIdModalFunc);
                }

                if (DOM.changeUserIdCancelBtn) {
                    DOM.changeUserIdCancelBtn.addEventListener('click', closeChangeUserIdModalFunc);
                }

                // Handle confirm button
                if (DOM.changeUserIdConfirmBtn) {
                    DOM.changeUserIdConfirmBtn.addEventListener('click', function() {
                        const newUserId = DOM.newUserIdInput.value.trim();
                        if (newUserId) {
                            localStorage.setItem('userId', newUserId);
                            closeChangeUserIdModalFunc();
                            // Optionally reload the page to apply the new user ID
                            // window.location.reload();
                        } else {
                            alert('Please enter a valid User ID');
                        }
                    });
                }

                // Close modal when clicking outside
                if (DOM.changeUserIdModal) {
                    DOM.changeUserIdModal.addEventListener('click', function(e) {
                        if (e.target === DOM.changeUserIdModal) {
                            closeChangeUserIdModalFunc();
                        }
                    });
                }
            }

            function open() {
                const currentUserId = localStorage.getItem('userId') || 'default';
                DOM.currentUserIdInput.value = currentUserId;
                DOM.newUserIdInput.value = '';
                DOM.changeUserIdModal.style.display = 'flex';
            }

            function close() {
                DOM.changeUserIdModal.style.display = 'none';
            }

            return { init, open, close };
        })(),

        AddInterviewee: (() => {
            function init() {
                // Event listeners are already set up in initEventListeners()
            }

            function open() {
                Modals._openModal(DOM.addIntervieweeModal);
                DOM.newIntervieweeName.focus();
            }

            function close() {
                Modals._closeModal(DOM.addIntervieweeModal);
                DOM.newIntervieweeName.value = '';
            }

            return { init, open, close };
        })(),

        MultiImageDisplay: (() => { 
            let currentGalleryImages = [];
            let currentGalleryIndex = 0;
            let imageModalElement = null;
            let imageModalImgElement = null;
            let imageModalVideoElement = null;
            let imageModalAudioElement = null;
            let imageModalPdfElement = null;

            const updateGalleryImage = () => {

              

                if (imageModalImgElement && currentGalleryImages.length > 0) {
                    const item = currentGalleryImages[currentGalleryIndex];

                    console.log("MuliImageDisplay updateGalleryImage called");
                    console.log(item);


                    debugger;
                    let src = "/getImage?id="+item.file_id
                    let alt = item.photo_description || `Image ${currentGalleryIndex + 1}`;
                    let srcType = item.file_type;
                    let file_extension = null;

                    // if the item is a string that start with /getImage?id= then set src to the item
                    if (typeof item === 'string' && item.startsWith('/getImage?id=')) {
                        src = item;
                        file_extension = src.split('ext=').pop(); 
                        file_extension = file_extension.trim();
                        file_extension = file_extension.toLowerCase();
                        file_extension = file_extension.replace('.', '');

                        if (file_extension === "jpg" || file_extension === "jpeg" || file_extension === "png" || file_extension === "gif" || file_extension === "webp") {
                            srcType = 'image';
                        }else if ( file_extension === "zip" || file_extension === "doc" || file_extension === "docx" || file_extension === "heic" || file_extension === "pptx" || file_extension === "ppt" || file_extension === "xls" || file_extension === "xlsx" || file_extension === "txt") {
                            srcType = 'image';
                            src = src+'&preview=true';
                        } else if (file_extension === "mp4" || file_extension === "mov" || file_extension === "avi" || file_extension === "mkv" || file_extension === "webm") {
                            srcType = 'video';
                        } else if (file_extension === "mp3" || file_extension === "wav" || file_extension === "ogg" || file_extension === "m4a" || file_extension === "aac" || file_extension === "opus") {
                            srcType = 'audio';
                        } else if (file_extension === "pdf") {
                            srcType = 'pdf';
                        }
                    } else  if (!item.file_id) {
                        src = item;
                        if (typeof item === 'string' && item.startsWith('/getImage?id=')) {
                            file_extension = src.split('ext=').pop(); 
                        } else {
                            file_extension = src.split('.').pop();
                        }
                    
                        if (file_extension === "jpg" || file_extension === "jpeg" || file_extension === "png" || file_extension === "gif" || file_extension === "webp") {
                            srcType = 'image';
                        }else if ( file_extension === "zip" || file_extension === "doc" || file_extension === "docx" || file_extension === "heic" || file_extension === "pptx" || file_extension === "ppt" || file_extension === "xls" || file_extension === "xlsx" || file_extension === "txt") {
                            srcType = 'image';
                            src = src+'&preview=true';
                        }else if (file_extension === "mp4" || file_extension === "mov" || file_extension === "avi" || file_extension === "mkv" || file_extension === "webm") {
                            srcType = 'video';
                        } else if (file_extension === "mp3" || file_extension === "wav" || file_extension === "ogg" || file_extension === "m4a" || file_extension === "aac" || file_extension === "opus") {
                            srcType = 'audio';
                        } else if (file_extension === "pdf") {
                            srcType = 'pdf';
                        }
                    }
                
                    imageModalVideoElement.style.display = 'none';
                    imageModalAudioElement.style.display = 'none';
                    imageModalImgElement.style.display = 'none';
                    imageModalPdfElement.style.display = 'none';

                    if (srcType === 'image') {
                        imageModalImgElement.src = src;
                        imageModalImgElement.alt = alt;
                        imageModalImgElement.style.display = 'block';
                    } else if (srcType === 'video') {
                        imageModalVideoElement.src = src;
                        imageModalVideoElement.alt = alt;
                        imageModalVideoElement.style.display = 'block';
                        imageModalVideoElement.controls = true;
                        imageModalVideoElement.autoplay = true;
                        imageModalVideoElement.loop = true;
                        imageModalVideoElement.muted = false;
                        imageModalVideoElement.playsinline = true;
                        imageModalVideoElement.style.width = '100%';
                        imageModalVideoElement.style.height = '100%';
                        imageModalVideoElement.style.objectFit = 'contain';
                    } else if (srcType === 'audio') {
                        imageModalAudioElement.src = src;
                        imageModalAudioElement.alt = alt;
                        imageModalAudioElement.controls = true;
                        imageModalAudioElement.autoplay = true;
                        imageModalAudioElement.style.objectFit = 'contain';
                        imageModalAudioElement.style.display = 'block';
                    } else if (srcType === 'pdf') {
                        imageModalPdfElement.src = src;
                        imageModalPdfElement.alt = alt;
                        imageModalPdfElement.style.display = 'block';
                        imageModalPdfElement.style.width = '100%';
                        imageModalPdfElement.style.height = '100%';
                    }
                }
            };
            


            function closeImageGalleryModal() {
                if (imageModalElement) {
                    imageModalElement.remove();
                    imageModalElement = null;
                    imageModalImgElement = null;
                }
                document.removeEventListener('keydown', handleGalleryKeyPress);
            }

            // Shows a gallery for image attachments in messages
            function showMultiImageModal(images, currentImageUri) {
                closeImageGalleryModal(); // Close any existing

                currentGalleryImages = images;
                currentGalleryIndex = images.findIndex(img => (img.file_id || img) === currentImageUri);
                if (currentGalleryIndex === -1) currentGalleryIndex = 0;

                imageModalElement = document.createElement('div');
                imageModalElement.className = 'image-modal';
                
                imageModalImgElement = document.createElement('img');
                imageModalVideoElement = document.createElement('video');
                imageModalAudioElement = document.createElement('audio');
                imageModalPdfElement = document.createElement('iframe');
                // updateGalleryImage will set src and alt

                const closeBtn = document.createElement('button');
                closeBtn.className = 'modal-close';
                closeBtn.innerHTML = '×';
                closeBtn.onclick = closeImageGalleryModal;
                imageModalElement.appendChild(closeBtn);

                // Add download button
                const downloadBtn = document.createElement('button');
                downloadBtn.className = 'download-btn';
                downloadBtn.style.position = 'absolute';
                downloadBtn.style.top = '15px';
                downloadBtn.style.right = '60px';
                downloadBtn.style.zIndex = '1001';
                downloadBtn.innerHTML = '<i class="fas fa-download"></i> Download';
                downloadBtn.title = 'Download this item';
                downloadBtn.onclick = _downloadCurrentMultiImageItem;
                imageModalElement.appendChild(downloadBtn);

                if (currentGalleryImages.length > 1) {
                    const prevBtn = document.createElement('button');
                    prevBtn.className = 'nav-arrow prev';
                    prevBtn.innerHTML = '❮';
                    prevBtn.onclick = (e) => {
                        e.stopPropagation();
                        currentGalleryIndex = (currentGalleryIndex - 1 + currentGalleryImages.length) % currentGalleryImages.length;
                        updateGalleryImage();
                    };
                    imageModalElement.appendChild(prevBtn);

                    const nextBtn = document.createElement('button');
                    nextBtn.className = 'nav-arrow next';
                    nextBtn.innerHTML = '❯';
                    nextBtn.onclick = (e) => {
                        e.stopPropagation();
                        currentGalleryIndex = (currentGalleryIndex + 1) % currentGalleryImages.length;
                        updateGalleryImage();
                    };
                    imageModalElement.appendChild(nextBtn);
                }
                
                imageModalElement.appendChild(imageModalImgElement);
                imageModalElement.appendChild(imageModalVideoElement);
                imageModalElement.appendChild(imageModalAudioElement);
                imageModalElement.appendChild(imageModalPdfElement);
                document.body.appendChild(imageModalElement);
                updateGalleryImage(); // Set initial image

                imageModalElement.addEventListener('click', (e) => {
                    if (e.target === imageModalElement) closeImageGalleryModal();
                });
                document.addEventListener('keydown', handleGalleryKeyPress);
            }

            
            function closeTileModal() {
                DOM.multiImageContainer.innerHTML = '';
                Modals._closeModal(DOM.fbImageModal);
            }

            function _downloadCurrentMultiImageItem() {
                if (currentGalleryImages.length === 0 || currentGalleryIndex < 0) {
                    console.error('No file information available for download');
                    return;
                }

                const currentItem = currentGalleryImages[currentGalleryIndex];
                let file_id = '';
                let filename = 'download';

                // Extract file_id and filename from the current item
                if (typeof currentItem === 'string' && currentItem.startsWith('/getImage?id=')) {
                    file_id = currentItem.split('=')[1];
                    filename = file_id;
                } else if (currentItem.file_id) {
                    file_id = currentItem.file_id;
                    filename = currentItem.file || currentItem.photo_description || file_id;
                } else {
                    console.error('Unable to determine file information for download');
                    return;
                }

                // Use the download endpoint
                let downloadUrl = `/downloadFile?id=${file_id}`;

                // Create a temporary link element to trigger download
                const link = document.createElement('a');
                link.href = downloadUrl;
                link.download = filename;
                link.target = '_blank';
                
                // Append to body, click, and remove
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }

            const handleGalleryKeyPress = (e) => {
                if (!imageModalElement) return;
                if (e.key === 'ArrowLeft' && currentGalleryImages.length > 1) {
                    currentGalleryIndex = (currentGalleryIndex - 1 + currentGalleryImages.length) % currentGalleryImages.length;
                    updateGalleryImage();
                } else if (e.key === 'ArrowRight' && currentGalleryImages.length > 1) {
                    currentGalleryIndex = (currentGalleryIndex + 1) % currentGalleryImages.length;
                    updateGalleryImage();
                } else if (e.key === 'Escape') {
                    closeImageGalleryModal();
                }
            };         
            
            const handleKeydownForTileModal = (event) => {
                if (event.key === 'Escape' && DOM.fbImageModal.style.display === 'flex') {
                    closeTileModal();
                }
            };

            function init() {
                if (DOM.multiImageModalCloseBtn) DOM.multiImageModalCloseBtn.addEventListener('click', closeTileModal);
                DOM.fbImageModal.addEventListener('click', (e) => { if (e.target === DOM.fbImageModal) closeTileModal(); });
                document.addEventListener('keydown', handleKeydownForTileModal);
            }

            return { init, showMultiImageModal };
        })(),

        SingleImageDisplay: (() => {
            let currentFileInfo = null; // Store current file information for download
            
            function init() {
                // The modal is already in the HTML, just need to ensure proper event handling
                if (DOM.singleImageModal) {
                    DOM.singleImageModal.addEventListener('click', (e) => {
                        if (e.target === DOM.singleImageModal) {
                            _close();
                        }
                    });
                }
                if (DOM.closeSingleImageModalBtn) {
                    DOM.closeSingleImageModalBtn.addEventListener('click', _close);
                }
                
                if (DOM.downloadSingleImageBtn) {
                    DOM.downloadSingleImageBtn.addEventListener('click', _downloadCurrentItem);
                }
                
                // Add keyboard support for Escape key
                document.addEventListener('keydown', (e) => {
                    if (e.key === 'Escape' && DOM.singleImageModal.style.display === 'flex') {
                        _close();
                    }
                });
            }

            function showSingleImageModal(filename, file_id, taken, lat, long) {
                if (!DOM.singleImageModal || !DOM.singleImageModalImg || !DOM.singleImageDetails) {
                    console.error('SingleImage modal elements not found');
                    return;
                }
                
                // Store current file information for download
                currentFileInfo = { filename, file_id, taken, lat, long };
                
                DOM.singleImageModalAudio.style.display = 'none';
                DOM.singleImageModalVideo.style.display = 'none';
                DOM.singleImageModalPdf.style.display = 'none';
                DOM.singleImageModalImg.style.display = 'none';

                // Set the image source

                if (file_id.endsWith('mp3') || file_id.endsWith('wav') || file_id.endsWith('ogg') || file_id.endsWith('m4a') || file_id.endsWith('aac') || file_id.endsWith('opus')) {
                    DOM.singleImageModalAudio.src = file_id;
                    DOM.singleImageModalAudio.style.display = 'block';
                    DOM.singleImageModalAudio.style.width = '400px';
                    DOM.singleImageModalAudio.style.height = '50px';
                    DOM.singleImageModalAudio.controls = true;
                    DOM.singleImageModalAudio.autoplay = true;
                    DOM.singleImageModalAudio.muted = false;
                    DOM.singleImageModalAudio.style.objectFit = 'contain';
                } else if (file_id.endsWith('mp4')) {
                    DOM.singleImageModalVideo.src = file_id;
                    DOM.singleImageModalVideo.style.display = 'block';
                } else if (file_id.endsWith('pdf')) {
                    DOM.singleImageModalPdf.src = file_id;
                    DOM.singleImageModalPdf.style.display = 'block';
                }else if (file_id.endsWith('doc') || file_id.endsWith('docx') || file_id.endsWith('zip') || file_id.endsWith('pptx') || file_id.endsWith('ppt') || file_id.endsWith('xls') || file_id.endsWith('xlsx') || file_id.endsWith('txt')) {
                    if (file_id.startsWith('/getImage')) {
                        DOM.singleImageModalImg.src = file_id+'&preview=true';
                    } else {
                        DOM.singleImageModalImg.src = '/getImage?id=' + file_id+'&preview=true';
                    }
                    DOM.singleImageModalImg.style.display = 'block';
                } else {
                    if (file_id.startsWith('/getImage')) {
                        DOM.singleImageModalImg.src = file_id;
                    } else {
                        DOM.singleImageModalImg.src = '/getImage?id=' + file_id;
                    }
                    DOM.singleImageModalImg.style.display = 'block';
                }


                // Set the details
                //DOM.singleImageDetails.innerHTML = `<p>${filename}</p><p>Taken: ${taken}</p><p>Latitude: ${lat}, Longitude: ${long}</p>`;

                // Show the modal
                Modals._openModal(DOM.singleImageModal);
            }

            function _downloadCurrentItem() {
                if (!currentFileInfo) {
                    console.error('No file information available for download');
                    return;
                }

                const { filename, file_id } = currentFileInfo;
                
                // Use the download endpoint for all file types
                //let downloadUrl = '/downloadFile?id=' + file_id;
                let downloadUrl = file_id.replace('getImage', 'downloadFile');

                // Create a temporary link element to trigger download
                const link = document.createElement('a');
                link.href = downloadUrl;
                link.download = filename || 'download';
                link.target = '_blank';
                
                // Append to body, click, and remove
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }

            function _close() {
                // Stop any playing audio
                if (DOM.singleImageModalAudio) {
                    DOM.singleImageModalAudio.pause();
                    DOM.singleImageModalAudio.currentTime = 0;
                }
                
                // Stop any playing video
                if (DOM.singleImageModalVideo) {
                    DOM.singleImageModalVideo.pause();
                    DOM.singleImageModalVideo.currentTime = 0;
                }
                
                // Clear PDF viewer
                if (DOM.singleImageModalPdf) {
                    DOM.singleImageModalPdf.src = '';
                }
                
                // Clear current file info
                currentFileInfo = null;
                
                Modals._closeModal(DOM.singleImageModal);
            }

            return { init, showSingleImageModal};
        })(),

        initAll: () => {
            Modals.Suggestions.init();
            Modals.FBAlbums.init();
            Modals.MultiImageDisplay.init();
            Modals.HaveYourSay.init();
            Modals.Locations.init();
            Modals.ImageGallery.init();
            Modals.EmailGallery.init();
            Modals.SMSMessages.init();
            Modals.SingleImageDisplay.init();
            Modals.ConfirmationModal.init();
            Modals.ChangeUserId.init();
            Modals.AddInterviewee.init();
        }
    };

    // --- SSE Module ---
    const SSE = (() => {
        const browserFunctions = { // Functions Gemini can ask the browser to execute
            showAlert: function(message) {
                alert(message);
                _logToChatbox(`Browser: Executed showAlert: "${message}"`);
            },
            changeBackgroundColor: function(color) {
                document.body.style.backgroundColor = color;
                _logToChatbox(`Browser: Executed changeBackgroundColor to "${color}"`);
            },
            showLocationInfo: function() {
                Modals.ConfirmationModal.open('Location Info', 'Would you like to see the location information mapped out?', () => {
                    Modals.Locations.openMapView();
                });
            },
            showFacebookAlbums: function() {
                Modals.ConfirmationModal.open('Facebook Albums', 'Would you like to choose the Facebook Albums to display?', () => {
                    Modals.FBAlbums.open();
                });
            },
            showImageGallery: function() {
                Modals.ConfirmationModal.open('Image Gallery', 'Would you like to choose the Image Gallery to display?', () => {
                    Modals.ImageGallery.open();
                });
            },
            showEmailGallery: function() {
                Modals.ConfirmationModal.open('Email Gallery', 'Would you like to browse through emails?', () => {
                    Modals.EmailGallery.open();
                });
            },
            showFacebookAlbum: function(albumTitle) {
                Modals.FBAlbums.openAlbum(albumTitle);
            },
            showContactEmailGallery: function(contactName) {
                Modals.EmailGallery.openContact(contactName);
            },
            testEmail: function() {
                const emailData = {
                    from: "sender@example.com",
                    to: "recipient@example.com",
                    subject: "Important Meeting Tomorrow",
                    date: "2024-01-15 14:30:00",
                    body_text: "Hi there,\n\nJust a reminder about our meeting tomorrow at 10 AM.\n\nBest regards,\nJohn",
                    attachments: [
                        { filename: "meeting_notes.pdf", size: 1024000 },
                        { filename: "agenda.docx", size: 512000 }
                    ]
                };
                
                Chat.addEmail(emailData);
            },
            // Add more functions here
        };

        function _logToChatbox(message) { // SSE specific logging, could be Chat.addMessage('system', ...)
            const p = document.createElement('p');
            p.textContent = message;
            DOM.chatBox.appendChild(p);
            UI.scrollToBottom();
        }

        function setup() {
            if (AppState.sseEventSource) AppState.sseEventSource.close(); // Close existing before opening new

            AppState.sseEventSource = new EventSource(`${CONSTANTS.API_PATHS.EVENTS}?clientId=${AppState.clientId}`);
            AppState.sseEventSource.onopen = () => {  console.log("SSE Connection Opened with clientId:", AppState.clientId);};
            AppState.sseEventSource.onmessage = (event) => {
                console.log("SSE Message Received:", event.data);
       
                try {
                    const data = JSON.parse(event.data);
                    if (data.action === "execute_js" && data.functionName && browserFunctions[data.functionName]) {
                        //_logToChatbox(`Browser: Received command to execute ${data.functionName}`);
                        browserFunctions[data.functionName].apply(null, Array.isArray(data.args) ? data.args : (data.args != null ? [data.args] : []));
                    } else {
                       // _logToChatbox(`Browser: Unknown function or invalid action requested: ${data.functionName}`);
                        console.warn("Unknown function or invalid action requested by backend:", data);
                    }
                } catch (e) {
                    console.error("Error parsing SSE message or executing function:", e);
                    //_logToChatbox(`Browser: Error processing command from server.`);
                }
            };
            AppState.sseEventSource.onerror = (err) => {
                //_logToChatbox("SSE Error. Connection may be closed.");
                console.error("EventSource failed:", err);
                // EventSource attempts to reconnect automatically.
            };
        }
        
        function close() {
            if (AppState.sseEventSource) {
                AppState.sseEventSource.close();
                console.log("SSE Connection Closed.");
            }
        }

        function init() {
          //  _logToChatbox(`Client ID: ${AppState.clientId}`);
            setup();
        }
        return { init, close, browserFunctions }; // Expose browserFunctions if needed elsewhere
    })();

    // --- Global Interviewee Management Functions ---
    async function loadInterviewees() {
        try {
            const response = await fetch('/interviewer/interviewees');
            const data = await response.json();
            
            if (data.interviewees) {
                // Clear existing options
                DOM.intervieweeSelect.innerHTML = '';
                
                // Add options for each interviewee
                data.interviewees.forEach(interviewee => {
                    const option = document.createElement('option');
                    option.value = interviewee;
                    option.textContent = interviewee;
                    if (interviewee === data.current_interviewee) {
                        option.selected = true;
                    }
                    DOM.intervieweeSelect.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Error loading interviewees:', error);
            // Use a more generic error display since we're not in interviewer mode yet
            console.error('Failed to load interviewees');
        }
    }

    async function switchInterviewee(subjectName) {
        try {
            const response = await fetch('/interviewer/switchinterviewee', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ subject_name: subjectName })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Update the UI to reflect the new interviewee
                await loadInterviewees();
                
                // Update the page title
                document.title = `Interviewer - ${subjectName}`;
                
                // Update the header title
                const interviewerHeaderTitle = document.querySelector('.interviewer-header-left h2');
                if (interviewerHeaderTitle) {
                    interviewerHeaderTitle.textContent = `Interview Mode - ${subjectName}`;
                }
                
                // Clear the interviewer chat window
                clearInterviewerChat();
                
                // Fetch the new interview state and update button controls
                try {
                    const interviewData = await fetchInterviewState();
                    AppState.interviewState = interviewData.interview_state;
                    updateInterviewControlButtons();
                } catch (error) {
                    console.error('Failed to fetch interview state after switch:', error);
                    AppState.interviewState = 'initial';
                    updateInterviewControlButtons();
                }
                
                // Add a system message indicating the switch
                addInterviewerMessage('system', `Switched to interviewee: ${subjectName}`, false);
                
                console.log(`Switched to interviewee: ${data.current_interviewee}`);
            } else {
                console.error(data.error || 'Failed to switch interviewee');
            }
        } catch (error) {
            console.error('Error switching interviewee:', error);
        }
    }

    async function addNewInterviewee(subjectName) {
        try {
            const response = await fetch('/interviewer/addinterviewee', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ subject_name: subjectName })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Update the interviewee list
                await loadInterviewees();
                
                // Update the page title
                document.title = `Interviewer - ${subjectName}`;
                
                // Update the header title
                const interviewerHeaderTitle = document.querySelector('.interviewer-header-left h2');
                if (interviewerHeaderTitle) {
                    interviewerHeaderTitle.textContent = `Interview Mode - ${subjectName}`;
                }
                
                // Clear the interviewer chat window
                clearInterviewerChat();
                
                // Fetch the new interview state and update button controls
                try {
                    const interviewData = await fetchInterviewState();
                    AppState.interviewState = interviewData.interview_state;
                    updateInterviewControlButtons();
                } catch (error) {
                    console.error('Failed to fetch interview state after adding interviewee:', error);
                    AppState.interviewState = 'initial';
                    updateInterviewControlButtons();
                }
                
                // Add a system message indicating the new interviewee
                addInterviewerMessage('system', `Added new interviewee: ${subjectName}`, false);
                
                console.log(`Added new interviewee: ${data.current_interviewee}`);
                
                // Close the modal
                Modals.AddInterviewee.close();
            } else {
                console.error(data.error || 'Failed to add interviewee');
            }
        } catch (error) {
            console.error('Error adding interviewee:', error);
        }
    }

    function handleIntervieweeSelectChange() {
        const selectedInterviewee = DOM.intervieweeSelect.value;
        if (selectedInterviewee) {
            switchInterviewee(selectedInterviewee);
        }
    }

    function handleAddIntervieweeClick() {
        Modals.AddInterviewee.open();
    }

    function handleAddIntervieweeSubmit() {
        const newName = DOM.newIntervieweeName.value.trim();
        if (newName) {
            addNewInterviewee(newName);
        } else {
            console.error('Please enter a valid interviewee name');
        }
    }

    function handleAddIntervieweeCancel() {
        Modals.AddInterviewee.close();
    }

    // --- Interviewer Mode Module ---
    const InterviewerMode = (() => {
        async function toggleInterviewerMode() {
            console.log('toggleInterviewerMode called');
            AppState.isInterviewerMode = !AppState.isInterviewerMode;
            
            if (AppState.isInterviewerMode) {
                console.log('Switching to interviewer mode');
                
                // Fetch current interview state from API
                try {
                    const interviewData = await fetchInterviewState();
                    AppState.interviewState = interviewData.interview_state;
                    AppState.interviewSubjectName = interviewData.subject_name;
                    
                    // Update the interviewer header title with subject name
                    const interviewerHeaderTitle = document.querySelector('.interviewer-header-left h2');
                    if (interviewerHeaderTitle) {
                        interviewerHeaderTitle.textContent = `Interview Mode - ${interviewData.subject_name}`;
                    }
                    
                    // Update the page title
                    document.title = `Interviewer - ${interviewData.subject_name}`;
                    
                    console.log('Interview state loaded:', interviewData);
                } catch (error) {
                    console.error('Failed to fetch interview state:', error);
                    AppState.interviewState = 'initial';
                    AppState.interviewSubjectName = 'Dave';
                }
                
                // Switch to interviewer mode
                DOM.chatMain.style.display = 'none';
                DOM.interviewerMain.style.display = 'flex';
                DOM.interviewerModeBtn.classList.add('active');
                document.body.classList.add('interviewer-mode');
                
                // Hide voice selector in interviewer mode
                const voiceSelector = document.querySelector('.voice-selector');
                if (voiceSelector) {
                    voiceSelector.style.display = 'none';
                }
                
                // Show interview control section
                const interviewControlSection = document.querySelector('.interview-control-section');
                if (interviewControlSection) {
                    interviewControlSection.style.display = 'block';
                }
                
                // Update button controls based on actual interview state
                updateInterviewControlButtons(true);
                
                // Clear any existing chat
                Chat.clearChat();
                
                // Focus on interviewer input
                DOM.interviewerUserInput.focus();
            } else {
                console.log('Switching back to normal mode');
                // Switch back to normal mode
                DOM.interviewerMain.style.display = 'none';
                DOM.chatMain.style.display = 'flex';
                DOM.interviewerModeBtn.classList.remove('active');
                document.body.classList.remove('interviewer-mode');
                
                // Reset the page title
                document.title = 'Talk About Dave';
                
                // Show voice selector again
                const voiceSelector = document.querySelector('.voice-selector');
                if (voiceSelector) {
                    voiceSelector.style.display = 'block';
                }
                
                // Hide interview control section
                const interviewControlSection = document.querySelector('.interview-control-section');
                if (interviewControlSection) {
                    interviewControlSection.style.display = 'none';
                }
                
                // Clear interviewer chat
                DOM.interviewerChatBox.innerHTML = '';
                
                // Show info box again
                DOM.infoBox.classList.remove('hidden');
                if (!DOM.chatBox.contains(DOM.infoBox)) {
                    DOM.chatBox.appendChild(DOM.infoBox);
                }
                
                // Reset interview state
                AppState.interviewState = 'initial';
                AppState.interviewSubjectName = 'Dave';
            }
        }

        function addInterviewerMessage(role, text, isMarkdown = true, messageId = null, embeddedJson = null) {
            const messageElement = document.createElement('div');
            messageElement.classList.add('message', role === 'suggestion' ? 'user-message' : `${role}-message`);
            if (role === 'suggestion') messageElement.style.backgroundColor = "#f4f778";
            if (messageId) messageElement.id = messageId;

            const contentElement = document.createElement('div');
            contentElement.classList.add('message-content');
            contentElement.dataset.role = (role === 'suggestion') ? "user" : role;
            if (role === 'suggestion') contentElement.style.backgroundColor = "#f4f778";

            if ((isMarkdown && role !== 'user') || role === 'suggestion') {
                const rawMarkdown = document.createElement('textarea');
                rawMarkdown.className = 'raw-markdown';
                rawMarkdown.style.display = 'none';
                rawMarkdown.value = text;
                contentElement.appendChild(rawMarkdown);
                Chat.renderMarkdown(contentElement, text);
            } else {
                contentElement.textContent = text;
            }

            // Add copy button
            const copyButton = document.createElement('button');
            copyButton.className = 'copy-hover-btn';
            copyButton.innerHTML = '<i class="fa-regular fa-copy"></i> Copy';
            copyButton.addEventListener('click', async () => {
                try {
                    let textToCopy = text;
                    if (['assistant', 'model', 'system'].includes(role)) {
                        const rawMarkdown = contentElement.querySelector('.raw-markdown');
                        textToCopy = rawMarkdown ? rawMarkdown.value : text;
                    }
                    await navigator.clipboard.writeText(textToCopy);
                    copyButton.innerHTML = '<i class="fa-solid fa-check"></i> Copied!';
                    copyButton.classList.add('copied');
                    setTimeout(() => {
                        copyButton.innerHTML = '<i class="fa-regular fa-copy"></i> Copy';
                        copyButton.classList.remove('copied');
                    }, 2000);
                } catch (err) {
                    console.error('Failed to copy text:', err);
                    copyButton.innerHTML = '<i class="fa-solid fa-xmark"></i> Failed';
                    copyButton.classList.add('error');
                    setTimeout(() => {
                        copyButton.innerHTML = '<i class="fa-regular fa-copy"></i> Copy';
                        copyButton.classList.remove('error');
                    }, 2000);
                }
            });
            messageElement.appendChild(copyButton);

            messageElement.appendChild(contentElement);
            DOM.interviewerChatBox.appendChild(messageElement);
            
            // Scroll to bottom
            setTimeout(() => { 
                DOM.interviewerChatBox.scrollTop = DOM.interviewerChatBox.scrollHeight; 
            }, 50);
            
            return messageElement;
        }

        function clearInterviewerChat() {
            DOM.interviewerChatBox.innerHTML = '';
            // Re-add info box
            const infoBox = document.getElementById('interviewer-info-box');
            if (infoBox) {
                DOM.interviewerChatBox.appendChild(infoBox);
            }
        }

        function setInterviewerControlsEnabled(enabled) {
            DOM.interviewerUserInput.disabled = !enabled;
            DOM.interviewerSendButton.disabled = !enabled;
        }

        function showInterviewerLoadingIndicator() {
            DOM.interviewerLoadingIndicator.style.display = 'flex';
        }

        function hideInterviewerLoadingIndicator() {
            DOM.interviewerLoadingIndicator.style.display = 'none';
        }

        function displayInterviewerError(message) {
            console.error("Interviewer Error displayed:", message);
            DOM.interviewerErrorDisplay.textContent = `Error: ${message}`;
            DOM.interviewerErrorDisplay.style.display = 'block';
            DOM.interviewerLoadingIndicator.style.display = 'none';
        }

        function clearInterviewerError() {
            DOM.interviewerErrorDisplay.textContent = '';
            DOM.interviewerErrorDisplay.style.display = 'none';
        }

        async function fetchInterviewState() {
            try {
                const response = await fetch('/interviewer/interviewstate');
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const data = await response.json();
                return data;
            } catch (error) {
                console.error('Error fetching interview state:', error);
                // Return default state if API call fails
                return {
                    interview_state: 'initial',
                    subject_name: 'Dave',
                    session_turns_count: 0,
                    session_tool_outputs_count: 0,
                    uploaded_files_count: 0
                };
            }
        }

        function updateInterviewControlButtons(just_switched_to_interviewer_mode = false) {
            // Disable all buttons first
            DOM.startInterviewBtn.disabled = true;
            DOM.resumeInterviewBtn.disabled = true;
            DOM.pauseInterviewBtn.disabled = true;
            DOM.writeInterimBioBtn.disabled = true;
            DOM.finishInterviewBtn.disabled = true;
            DOM.writeFinalBioBtn.disabled = true;
            DOM.resetInterviewBtn.disabled = true;

            // Enable buttons based on current interview state
            switch (AppState.interviewState) {
                case 'initial':
                    // Only enable Start Interview when interview state is initial
                    DOM.startInterviewBtn.disabled = false;
                    break;
                case 'active':
                    // Enable Pause Interview when interview is active
                    DOM.pauseInterviewBtn.disabled = false;
                    if (just_switched_to_interviewer_mode) {
                        DOM.resumeInterviewBtn.disabled = false;
                    }
                    DOM.resetInterviewBtn.disabled = false;
                    break;
                case 'paused':
                    // Enable Resume Interview, Write Interim Biography, and Finish Interview when paused
                    DOM.resumeInterviewBtn.disabled = false;
                    DOM.writeInterimBioBtn.disabled = false;
                    DOM.finishInterviewBtn.disabled = false;
                    DOM.resetInterviewBtn.disabled = false;
                    break;
                case 'finished':
                    // Enable Write Final Biography, Resume Interview, and Start Interview when interview is finished
                    DOM.writeFinalBioBtn.disabled = false;
                    DOM.resumeInterviewBtn.disabled = false;
                    DOM.startInterviewBtn.disabled = false;
                    DOM.resetInterviewBtn.disabled = false;
                    break;
            }
        }

        // Interviewer dictation functions
        function startInterviewerDictation() {
            if (!AppState.interviewerDictationRecognition) return;
            if (AppState.isInterviewerDictationListening) {
                stopInterviewerDictation();
                return;
            }
            AppState.finalInterviewerDictationTranscript = '';
            DOM.interviewerUserInput.value = '';
            AppState.interviewerDictationRecognition.start();
            DOM.interviewerStartDictationBtn.style.display = 'none';
            DOM.interviewerStopDictationBtn.style.display = 'block';
        }

        function stopInterviewerDictation() {
            if (!AppState.isInterviewerDictationListening) {
                return;
            }
            
            if (AppState.interviewerDictationRecognition) {
                AppState.interviewerDictationRecognition.stop();
            }
            DOM.interviewerStopDictationBtn.style.display = 'none';
            DOM.interviewerStartDictationBtn.style.display = 'block';
            AppState.isInterviewerDictationListening = false;
            
            // Auto-submit the entered text if there's content
            const userInput = DOM.interviewerUserInput.value.trim();
            if (userInput) {
                processInterviewerFormSubmit(userInput);
            }
        }

        function initInterviewerSpeechRecognition() {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (SpeechRecognition) {
                AppState.interviewerDictationRecognition = new SpeechRecognition();
                AppState.interviewerDictationRecognition.lang = 'en-US';
                AppState.interviewerDictationRecognition.interimResults = true;
                AppState.interviewerDictationRecognition.continuous = true;

                AppState.interviewerDictationRecognition.onstart = () => { 
                    AppState.isInterviewerDictationListening = true; 
                };
                AppState.interviewerDictationRecognition.onerror = (event) => { 
                    DOM.interviewerDictationStatus.textContent = 'Dictation error: ' + event.error; 
                    AppState.isInterviewerDictationListening = false; 
                    stopInterviewerDictation(); 
                };
                AppState.interviewerDictationRecognition.onend = () => { 
                    AppState.isInterviewerDictationListening = false; 
                    stopInterviewerDictation(); 
                };
                AppState.interviewerDictationRecognition.onresult = (event) => {
                    let interimTranscript = '';
                    for (let i = event.resultIndex; i < event.results.length; ++i) {
                        if (event.results[i].isFinal) {
                            AppState.finalInterviewerDictationTranscript += event.results[i][0].transcript;
                        } else {
                            interimTranscript += event.results[i][0].transcript;
                        }
                    }
                    DOM.interviewerUserInput.value = AppState.finalInterviewerDictationTranscript + interimTranscript;
                };
            } else {
                if (DOM.interviewerStartDictationBtn) {
                    DOM.interviewerStartDictationBtn.disabled = true;
                    DOM.interviewerDictationStatus.textContent = 'Speech recognition not supported.';
                }
            }
        }

        // ==================== INTERVIEWEE MANAGEMENT ====================
        
        // These functions are now in global scope above

        async function processInterviewerFormSubmit(userPrompt, category = null, title = null, supplementary_prompt = null) {
            if (!userPrompt && !category && !title) return;

            clearInterviewerError();
            setInterviewerControlsEnabled(false);
            showInterviewerLoadingIndicator();

            const selectedVoice = VoiceSelector.getSelectedVoice();
            const selectedMood = (selectedVoice === 'dave' && DOM.daveMood) ? DOM.daveMood.value : null;
            
            // Get selected interview purpose
            const selectedPurpose = DOM.interviewPurposeSelect ? DOM.interviewPurposeSelect.value : '';
            let purposeContext = '';
            
            if (selectedPurpose && !userPrompt.includes('biography')) {
                const purposeMap = {
                    'biography': 'biography writing',
                    'research': 'academic research',
                    'journalism': 'journalism/article writing',
                    'therapy': 'therapeutic session',
                    'oral-history': 'oral history documentation',
                    'memoir': 'memoir writing',
                    'documentary': 'documentary film',
                    'podcast': 'podcast interview',
                    'book': 'book research',
                    'personal': 'personal interest',
                    'family': 'family history',
                    'professional': 'professional development',
                    'creative': 'creative writing',
                    'other': 'the selected purpose'
                };
                purposeContext = ` (Context: This interview is for ${purposeMap[selectedPurpose] || 'the selected purpose'})`;
            }
            
            try {
                const finalMessage = UI.getWorkModePrefix() + userPrompt + purposeContext;

                if (category && title) {
                    addInterviewerMessage('suggestion', `**${category}:** ${title}`, true);
                } else {
                    addInterviewerMessage('user', userPrompt, false);
                }
                
                DOM.interviewerUserInput.value = '';

                const response = await ApiService.fetchChat({
                    prompt: finalMessage,
                    voice: selectedVoice,
                    mood: selectedMood,
                    interviewMode: true, // Always use interview mode for interviewer
                    companionMode: false,
                    supplementary_prompt: supplementary_prompt,
                    temperature: parseFloat(DOM.creativityLevel ? DOM.creativityLevel.value : '0'),
                    clientId: AppState.clientId
                });
                
                const data = await response.json();
                hideInterviewerLoadingIndicator();
                if (data.error) displayInterviewerError(data.error);
                else addInterviewerMessage('assistant', data.text, true, null, data.embedded_json);

            } catch (error) {
                console.error('Interviewer form submit error:', error);
                displayInterviewerError(error.message || 'An unknown error occurred.');
            } finally {
                setInterviewerControlsEnabled(true);
                hideInterviewerLoadingIndicator();
            }
        }

        function init() {
            // Initialize interviewer speech recognition
            initInterviewerSpeechRecognition();
            
            // Add event listeners for interviewer mode
            if (DOM.interviewerModeBtn) {
                console.log('Interviewer mode button found, adding event listener');
                DOM.interviewerModeBtn.addEventListener('click', async () => {
                    await toggleInterviewerMode();
                });
                
                // Add a simple test click handler
                DOM.interviewerModeBtn.addEventListener('click', () => {
                    console.log('Interviewer mode button clicked!');
                });
            } else {
                console.error('Interviewer mode button not found!');
            }
            
            if (DOM.interviewerChatForm) {
                DOM.interviewerChatForm.addEventListener('submit', (event) => {
                    event.preventDefault();
                    const userPrompt = DOM.interviewerUserInput.value.trim();
                    if (!userPrompt) return;
                    processInterviewerFormSubmit(userPrompt);
                });
            }
            
            if (DOM.interviewerUserInput) {
                DOM.interviewerUserInput.addEventListener('keydown', (event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                        event.preventDefault();
                        DOM.interviewerChatForm.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
                    }
                });
            }
            
            if (DOM.interviewerStartDictationBtn) {
                DOM.interviewerStartDictationBtn.addEventListener('click', startInterviewerDictation);
            }
            
            if (DOM.interviewerStopDictationBtn) {
                DOM.interviewerStopDictationBtn.addEventListener('click', stopInterviewerDictation);
            }
            
            if (DOM.exitInterviewerModeBtn) {
                DOM.exitInterviewerModeBtn.addEventListener('click', async () => {
                    await toggleInterviewerMode();
                });
            }
            
            // Add event listeners for interview control buttons
            if (DOM.startInterviewBtn) {
                DOM.startInterviewBtn.addEventListener('click', handleStartInterview);
            }
            
            if (DOM.resumeInterviewBtn) {
                DOM.resumeInterviewBtn.addEventListener('click', handleResumeInterview);
            }
            
            if (DOM.pauseInterviewBtn) {
                DOM.pauseInterviewBtn.addEventListener('click', handlePauseInterview);
            }
            
            if (DOM.writeInterimBioBtn) {
                DOM.writeInterimBioBtn.addEventListener('click', handleWriteInterimBio);
            }
            
            if (DOM.finishInterviewBtn) {
                DOM.finishInterviewBtn.addEventListener('click', handleFinishInterview);
            }
            
            if (DOM.writeFinalBioBtn) {
                DOM.writeFinalBioBtn.addEventListener('click', handleWriteFinalBio);
            }
            
            if (DOM.resetInterviewBtn) {
                DOM.resetInterviewBtn.addEventListener('click', handleResetInterview);
            }
            
            // Add event listener for interview purpose selector
            if (DOM.interviewPurposeSelect) {
                DOM.interviewPurposeSelect.addEventListener('change', handleInterviewPurposeChange);
            }

            // Initialize interviewee list
            loadInterviewees();
        }

        // Interview control button handlers
        async function handleStartInterview() {
            console.log('Start Interview clicked');
            
            try {
                // Check if there's existing interview data
                const checkResponse = await ApiService.checkInterviewData();
                const checkData = await checkResponse.json();
                
                if (checkData.has_data) {
                    // Show confirmation popup
                    Modals.ConfirmationModal.open(
                        'Start New Interview', 
                        `There is existing interview data (${checkData.turn_count} conversation turns). Starting a new interview will clear all existing data. Are you sure you want to continue?`,
                        async () => {
                            // User confirmed - proceed with starting new interview
                            await _performStartInterview();
                        }
                    );
                } else {
                    // No existing data - proceed directly
                    await _performStartInterview();
                }
            } catch (error) {
                console.error('Error checking interview data:', error);
                // If check fails, proceed anyway
                await _performStartInterview();
            }
        }

        async function _performStartInterview() {
            addInterviewerMessage('system', 'Starting new interview session. First thing I\'ll do is check your biography and decide how to proceed.', false);
            clearInterviewerError();
            setInterviewerControlsEnabled(false);
            showInterviewerLoadingIndicator();

            const response = await ApiService.startInterview();
            const data = await response.json();
            hideInterviewerLoadingIndicator();
            if (data.error) {
                displayInterviewerError(data.error);
            } else {
                addInterviewerMessage('assistant', data.text, true, null, data.embedded_json);
                // Update interview state to 'active' and enable appropriate buttons
                AppState.interviewState = 'active';
                updateInterviewControlButtons();
                setInterviewerControlsEnabled(true);
            }
        }

        async function handleResumeInterview() {
            console.log('Resume Interview clicked');
            addInterviewerMessage('system', 'Interview resumed.', false);
            clearInterviewerError();
            setInterviewerControlsEnabled(false);
            showInterviewerLoadingIndicator();

            const response = await ApiService.resumeInterview();
            const data = await response.json();
            hideInterviewerLoadingIndicator();
            if (data.error) {
                displayInterviewerError(data.error);
            } else {
                addInterviewerMessage('assistant', data.text, true, null, data.embedded_json);
                // Update interview state to 'active' and enable appropriate buttons
                AppState.interviewState = 'active';
                updateInterviewControlButtons();
                setInterviewerControlsEnabled(true);
            }
        }

        async function handlePauseInterview() {
            console.log('Pause Interview clicked');
            addInterviewerMessage('system', 'Interview paused. You can resume it later.', false);
            showInterviewerLoadingIndicator();
            const response = await ApiService.pauseInterview();
            const data = await response.json();
            hideInterviewerLoadingIndicator();
            if (data.error) {
                displayInterviewerError(data.error);
            } else {
                addInterviewerMessage('assistant', data.text, true, null, data.embedded_json);
                // Update interview state to 'paused' and enable appropriate buttons
                AppState.interviewState = 'paused';
                updateInterviewControlButtons();
                setInterviewerControlsEnabled(false);
            }
        }

        async function handleWriteInterimBio() {
            console.log('Write Interim Biography clicked');
            showInterviewerLoadingIndicator();
            const response = await ApiService.writeInterimBio();
            const data = await response.json();
            hideInterviewerLoadingIndicator();
            if (data.error) {
                displayInterviewerError(data.error);
            } else {
                addInterviewerMessage('assistant', data.text, true, null, data.embedded_json);
            }
        }

        function handleFinishInterview() {
            console.log('Finish Interview clicked');
            addInterviewerMessage('system', 'Interview finished. You can now write the final biography or exit interview mode.', false);
            // Update interview state to 'finished' and enable appropriate buttons
            AppState.interviewState = 'finished';
            updateInterviewControlButtons();
            // Disable input controls
            setInterviewerControlsEnabled(false);
        }

        async function handleWriteFinalBio() {
            console.log('Write Final Biography clicked');
            showInterviewerLoadingIndicator();
            const response = await ApiService.writeFinalBio();
            const data = await response.json();
            hideInterviewerLoadingIndicator();
            if (data.error) {
                displayInterviewerError(data.error);
            } else {
                addInterviewerMessage('assistant', data.text, true, null, data.embedded_json);
            }
        }

        async function handleResetInterview() {
            console.log('Reset Interview clicked');
            
            // Show confirmation dialog
            Modals.ConfirmationModal.open(
                'Reset Interview', 
                'This will permanently delete all interview data including conversation history, biography brief, and vector embeddings. This action cannot be undone. Are you sure you want to reset the interview?',
                async () => {
                    // User confirmed - proceed with reset
                    addInterviewerMessage('system', 'Resetting interview...', false);
                    clearInterviewerError();
                    setInterviewerControlsEnabled(false);
                    showInterviewerLoadingIndicator();

                    try {
                        const response = await ApiService.resetInterview();
                        const data = await response.json();
                        hideInterviewerLoadingIndicator();
                        
                        if (data.error) {
                            displayInterviewerError(data.error);
                            setInterviewerControlsEnabled(true);
                        } else {
                            // Clear the interviewer chat
                            clearInterviewerChat();
                            
                            // Update interview state to 'initial'
                            AppState.interviewState = 'initial';
                            updateInterviewControlButtons();
                            
                            // Show success message
                            addInterviewerMessage('system', 'Interview reset successfully. All data has been cleared. You can now start a new interview.', false);
                            setInterviewerControlsEnabled(true);
                        }
                    } catch (error) {
                        console.error('Error resetting interview:', error);
                        hideInterviewerLoadingIndicator();
                        displayInterviewerError('Failed to reset interview. Please try again.');
                        setInterviewerControlsEnabled(true);
                    }
                }
            );
        }

        function handleInterviewPurposeChange() {
            const selectedPurpose = DOM.interviewPurposeSelect.value;
            console.log('Interview purpose changed to:', selectedPurpose);
            
            if (selectedPurpose) {
                // Add a system message to indicate the interview purpose
                addInterviewerMessage('system', `Interview purpose set to: ${DOM.interviewPurposeSelect.options[DOM.interviewPurposeSelect.selectedIndex].text}`, false);
            }
        }

        return { 
            init, 
            toggleInterviewerMode, 
            addInterviewerMessage, 
            clearInterviewerChat, 
            processInterviewerFormSubmit,
            setInterviewerControlsEnabled,
            showInterviewerLoadingIndicator,
            hideInterviewerLoadingIndicator,
            displayInterviewerError,
            clearInterviewerError,
            updateInterviewControlButtons
        };
    })();

    // --- Application Actions (for dynamic function calls from suggestions.json) ---
    const AppActions = {
        [CONSTANTS.FUNCTION_NAMES.FirstFunction]: async () => { // getFacebookChatters
            UI.clearError();
            DOM.infoBox.classList.add('hidden');
            UI.setControlsEnabled(false);
            UI.showLoadingIndicator();
            try {
                const data = await ApiService.fetchFacebookChatters();
                let markdownText = '# Facebook Chat Statistics\n\n|Participant|Number of Messages|\n|-----|---|\n';
                for (const message of Object.values(data)) { // Iterate over values if data is an object
                    markdownText += `| ${message.participant[0].name} |${message.number_of_messages}|\n`;
                }
                Chat.addMessage('assistant', markdownText, true);
            } catch (error) {
                console.error('Error in getFacebookChatters:', error);
                UI.displayError("Failed to get FB chatters: " + error.message);
            } finally {
                UI.setControlsEnabled(true);
                UI.hideLoadingIndicator();
            }
        },
        [CONSTANTS.FUNCTION_NAMES.ThirdFunction]: () => Modals.FBAlbums.open(),    // showFBAlbumsOptions
        [CONSTANTS.FUNCTION_NAMES.FourthFunction]: () => Modals.Locations.open(), // showGeoMetadataOptions
        [CONSTANTS.FUNCTION_NAMES.FifthFunction]: () => SSE.browserFunctions.showLocationInfo(), // showTileAlbumOptions
        [CONSTANTS.FUNCTION_NAMES.SixthFunction]: () => Modals.ImageGallery.open(),
        [CONSTANTS.FUNCTION_NAMES.SeventhFunction]: () => SSE.browserFunctions.testEmail(), // showImageGalleryOptions
        [CONSTANTS.FUNCTION_NAMES.EighthFunction]: () => Modals.EmailGallery.open() // showEmailGalleryOptions

    };
    window.customObject = AppActions; // Expose for Suggestions.json if it relies on global `customObject`


    // --- Main Application Logic & Initialization ---
    const App = (() => {
        async function processFormSubmit(userPrompt, category = null, title = null, supplementary_prompt = null) {
            if (!userPrompt && !category && !title) return;

            UI.clearError();
            DOM.infoBox.classList.add('hidden');
            UI.setControlsEnabled(false);
            UI.showLoadingIndicator();

            const selectedVoice = VoiceSelector.getSelectedVoice();
            const selectedMood = (selectedVoice === 'dave' && DOM.daveMood) ? DOM.daveMood.value : null;
            
            try {
                const finalMessage = UI.getWorkModePrefix() + userPrompt;

                if (category && title) Chat.addMessage('suggestion', `**${category}:** ${title}`, true);
                else Chat.addMessage('user', userPrompt, false); // User messages are not markdown by default
                
                DOM.userInput.value = '';

                const currentUserId = localStorage.getItem('userId') || 'default';
                const response = await ApiService.fetchChat({
                    prompt: finalMessage,
                    voice: selectedVoice,
                    mood: selectedMood,
                    interviewMode: AppState.isInterviewerMode, // Use interviewer mode state instead of checkbox
                    companionMode: DOM.companionModeCheckbox ? DOM.companionModeCheckbox.checked : false,
                    supplementary_prompt: supplementary_prompt,
                    temperature: parseFloat(DOM.creativityLevel ? DOM.creativityLevel.value : '0'),
                    clientId: AppState.clientId,
                    userId:currentUserId
                });
                
                // Non-streaming JSON response handling (original code commented out streaming)
                const data = await response.json();
                UI.hideLoadingIndicator(); // Hide after getting response, before adding message
                if (data.error) UI.displayError(data.error);
                else Chat.addMessage('assistant', data.text, true, null, data.embedded_json);

            } catch (error) {
                console.error('Form submit error:', error);
                UI.displayError(error.message || 'An unknown error occurred.');
                // UI.hideLoadingIndicator(); // Already handled in displayError or finally
            } finally {
                UI.setControlsEnabled(true);
                UI.hideLoadingIndicator(); // Ensure it's hidden
            }
        }

        async function handleNewChat() {
            UI.clearError();
            UI.showLoadingIndicator();
            try {
                const data = await ApiService.fetchNewChat();
                if (data.status === 'ok') {
                    Chat.clearChat();
                    // Reset voice to expert and trigger its change logic
                    if (DOM.voiceSelect) {
                        DOM.voiceSelect.value = 'expert';
                        DOM.voiceSelect.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                    console.log('New chat started.');
                } else {
                    UI.displayError('Failed to start new chat on server.');
                }
            } catch (error) {
                console.error('New chat error:', error);
                UI.displayError(error.message || 'Could not start new chat.');
            } finally {
                UI.hideLoadingIndicator();
            }
        }

        function initEventListeners() {
            DOM.chatForm.addEventListener('submit', (event) => {
                event.preventDefault();
                const userPrompt = DOM.userInput.value.trim();
                if (!userPrompt) return;
                processFormSubmit(userPrompt);
            });

            DOM.newChatButton.addEventListener('click', handleNewChat);

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
            });
            DOM.closeConfigBtn.addEventListener('click', () => {
                DOM.configPage.style.display = 'none';
                DOM.chatMain.style.display = 'flex';
            });

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
                    
                    // Load folders when controls tab is opened
                    if (targetTab === 'controls') {
                        loadFolders();
                        checkInitialStatus();
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
                });
            });

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

            // iMessage Import Controls
            const startImessageImportBtn = document.getElementById('start-imessage-import-btn');
            const cancelImessageImportBtn = document.getElementById('cancel-imessage-import-btn');
            const imessageImportStatus = document.getElementById('imessage-import-status');
            const imessageImportStatusMessage = document.getElementById('imessage-import-status-message');
            const imessageImportStatusDetails = document.getElementById('imessage-import-status-details');
            const imessageImportProgressContainer = document.getElementById('imessage-import-progress-container');
            const imessageDirectoryPath = document.getElementById('imessage-directory-path');
            const imessageMissingAttachmentsList = document.getElementById('imessage-missing-attachments-list');
            const imessageMissingFilenames = document.getElementById('imessage-missing-filenames');
            let imessageImportInProgress = false;
            let imessageEventSource = null;

            // Show iMessage import status
            function showImessageImportStatus(type, message, details = '') {
                if (!imessageImportStatus) return;
                
                imessageImportStatus.classList.remove('success', 'error', 'info');
                imessageImportStatus.classList.add(type);
                imessageImportStatus.style.display = 'block';
                if (imessageImportStatusMessage) {
                    imessageImportStatusMessage.textContent = message;
                }
                if (imessageImportStatusDetails) {
                    imessageImportStatusDetails.textContent = details;
                }
            }

            // Close iMessage import SSE connection
            function closeImessageEventSource() {
                if (imessageEventSource) {
                    imessageEventSource.close();
                    imessageEventSource = null;
                }
            }

            // Connect to iMessage import SSE stream
            function connectToImessageProgressStream() {
                // Close existing connection if any
                closeImessageEventSource();

                // Create EventSource connection
                imessageEventSource = new EventSource('/imessages/import/stream');

                imessageEventSource.onmessage = (event) => {
                    try {
                        const eventData = JSON.parse(event.data);
                        handleImessageProgressEvent(eventData);
                    } catch (error) {
                        console.error('Error parsing iMessage SSE event:', error);
                    }
                };

                imessageEventSource.onerror = (error) => {
                    console.error('iMessage SSE connection error:', error);
                    // Don't close on error - EventSource will attempt to reconnect
                };

                // Clean up on page unload
                window.addEventListener('beforeunload', () => {
                    closeImessageEventSource();
                });
            }

            // Handle iMessage import progress events
            function handleImessageProgressEvent(eventData) {
                const { type, data } = eventData;

                switch (type) {
                    case 'progress':
                        updateImessageImportProgress(data);
                        if (data.status === 'in_progress') {
                            cancelImessageImportBtn.style.display = 'inline-block';
                            startImessageImportBtn.disabled = true;
                            showImessageImportStatus('info', 'Import in progress...', `Processing conversation ${data.conversations_processed} of ${data.total_conversations}`);
                        }
                        break;

                    case 'completed':
                        updateImessageImportProgress(data);
                        cancelImessageImportBtn.style.display = 'none';
                        startImessageImportBtn.disabled = false;
                        imessageImportInProgress = false;
                        const progressBar = document.getElementById('imessage-import-progress-bar');
                        const progressBarText = document.getElementById('imessage-progress-bar-text');
                        if (progressBar && progressBarText) {
                            progressBar.style.width = '100%';
                            progressBarText.textContent = '100%';
                        }
                        showImessageImportStatus(
                            'success',
                            'Import completed successfully',
                            `Processed ${data.conversations_processed} conversation(s). ` +
                            `Imported ${data.messages_imported} message(s) ` +
                            `(${data.messages_created} created, ${data.messages_updated} updated). ` +
                            `Found ${data.attachments_found} attachment(s), ` +
                            `${data.attachments_missing} missing, ` +
                            `${data.errors} error(s).`
                        );
                        if ('Notification' in window && Notification.permission === 'granted') {
                            new Notification('iMessage Import Complete', {
                                body: `Imported ${data.messages_imported} messages from ${data.conversations_processed} conversations.`,
                                icon: '/static/images/expert.png'
                            });
                        }
                        closeImessageEventSource();
                        break;

                    case 'error':
                        updateImessageImportProgress(data);
                        cancelImessageImportBtn.style.display = 'none';
                        startImessageImportBtn.disabled = false;
                        imessageImportInProgress = false;
                        showImessageImportStatus('error', 'Import error', data.error_message || 'An error occurred during import.');
                        if ('Notification' in window && Notification.permission === 'granted') {
                            new Notification('iMessage Import Error', {
                                body: data.error_message || 'An error occurred during import.',
                                icon: '/static/images/expert.png'
                            });
                        }
                        closeImessageEventSource();
                        break;

                    case 'cancelled':
                        updateImessageImportProgress(data);
                        cancelImessageImportBtn.style.display = 'none';
                        startImessageImportBtn.disabled = false;
                        imessageImportInProgress = false;
                        showImessageImportStatus('info', 'Import cancelled', data.error_message || 'Import was cancelled.');
                        if ('Notification' in window && Notification.permission === 'granted') {
                            new Notification('iMessage Import Cancelled', {
                                body: 'Import was cancelled by user.',
                                icon: '/static/images/expert.png'
                            });
                        }
                        closeImessageEventSource();
                        break;

                    case 'heartbeat':
                        // Keep connection alive - no UI update needed
                        break;

                    default:
                        console.log('Unknown iMessage event type:', type);
                }
            }

            // Update iMessage import progress
            function updateImessageImportProgress(stats) {
                if (!imessageImportProgressContainer) return;
                
                imessageImportProgressContainer.style.display = 'block';
                
                const currentConversationName = document.getElementById('current-conversation-name');
                const imessageProgressText = document.getElementById('imessage-progress-text');
                const imessageImportProgressBar = document.getElementById('imessage-import-progress-bar');
                const imessageProgressBarText = document.getElementById('imessage-progress-bar-text');
                const imessageMessagesImported = document.getElementById('imessage-messages-imported');
                const imessageMessagesCreated = document.getElementById('imessage-messages-created');
                const imessageMessagesUpdated = document.getElementById('imessage-messages-updated');
                const imessageAttachmentsFound = document.getElementById('imessage-attachments-found');
                const imessageAttachmentsMissing = document.getElementById('imessage-attachments-missing');
                const imessageErrors = document.getElementById('imessage-errors');

                if (currentConversationName) {
                    currentConversationName.textContent = stats.current_conversation || '-';
                }

                if (imessageProgressText && stats.total_conversations > 0) {
                    imessageProgressText.textContent = `${stats.conversations_processed} / ${stats.total_conversations}`;
                }

                if (imessageImportProgressBar && imessageProgressBarText && stats.total_conversations > 0) {
                    const percentage = Math.round((stats.conversations_processed / stats.total_conversations) * 100);
                    imessageImportProgressBar.style.width = `${percentage}%`;
                    imessageProgressBarText.textContent = `${percentage}%`;
                }

                if (imessageMessagesImported) {
                    imessageMessagesImported.textContent = stats.messages_imported || 0;
                }
                if (imessageMessagesCreated) {
                    imessageMessagesCreated.textContent = stats.messages_created || 0;
                }
                if (imessageMessagesUpdated) {
                    imessageMessagesUpdated.textContent = stats.messages_updated || 0;
                }
                if (imessageAttachmentsFound) {
                    imessageAttachmentsFound.textContent = stats.attachments_found || 0;
                }
                if (imessageAttachmentsMissing) {
                    imessageAttachmentsMissing.textContent = stats.attachments_missing || 0;
                }
                if (imessageErrors) {
                    imessageErrors.textContent = stats.errors || 0;
                }

                // Update missing attachment filenames
                if (stats.missing_attachment_filenames && stats.missing_attachment_filenames.length > 0) {
                    if (imessageMissingAttachmentsList) {
                        imessageMissingAttachmentsList.style.display = 'block';
                    }
                    if (imessageMissingFilenames) {
                        imessageMissingFilenames.innerHTML = stats.missing_attachment_filenames
                            .map(filename => `<div style="margin-bottom: 4px;">${filename}</div>`)
                            .join('');
                    }
                } else {
                    if (imessageMissingAttachmentsList) {
                        imessageMissingAttachmentsList.style.display = 'none';
                    }
                }
            }

            // Check initial iMessage import status
            async function checkInitialImessageStatus() {
                if (!imessageImportStatus) return;
                
                try {
                    const response = await fetch('/imessages/import/status');
                    if (!response.ok) {
                        return;
                    }
                    const status = await response.json();
                    
                    if (status.in_progress) {
                        cancelImessageImportBtn.style.display = 'inline-block';
                        startImessageImportBtn.disabled = true;
                        imessageImportInProgress = true;
                        // Connect to stream to get updates
                        connectToImessageProgressStream();
                        updateImessageImportProgress(status);
                    } else {
                        cancelImessageImportBtn.style.display = 'none';
                        startImessageImportBtn.disabled = false;
                        imessageImportInProgress = false;
                    }
                } catch (error) {
                    console.error('Error checking initial iMessage import status:', error);
                }
            }

            // Start iMessage import
            if (startImessageImportBtn) {
                startImessageImportBtn.addEventListener('click', async () => {
                    const directoryPath = imessageDirectoryPath?.value?.trim();
                    
                    if (!directoryPath) {
                        showImessageImportStatus('error', 'Directory path required', 'Please enter a directory path.');
                        return;
                    }
                    
                    if (imessageImportInProgress) {
                        showImessageImportStatus('error', 'Import already in progress', 'Please wait for the current import to complete.');
                        return;
                    }
                    
                    try {
                        imessageImportInProgress = true;
                        startImessageImportBtn.disabled = true;
                        cancelImessageImportBtn.style.display = 'inline-block';
                        showImessageImportStatus('info', 'Starting import...', 'Sending request to server...');
                        
                        // Clear previous missing filenames
                        if (imessageMissingFilenames) {
                            imessageMissingFilenames.innerHTML = '';
                        }
                        if (imessageMissingAttachmentsList) {
                            imessageMissingAttachmentsList.style.display = 'none';
                        }
                        
                        updateImessageImportProgress({
                            conversations_processed: 0,
                            total_conversations: 0,
                            messages_imported: 0,
                            messages_created: 0,
                            messages_updated: 0,
                            attachments_found: 0,
                            attachments_missing: 0,
                            missing_attachment_filenames: [],
                            errors: 0
                        });
                        
                        const response = await fetch('/imessages/import', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({
                                directory_path: directoryPath
                            })
                        });
                        
                        const result = await response.json();
                        
                        if (response.ok) {
                            showImessageImportStatus('info', 'Import started', result.message || 'iMessage import has been initiated.');
                            
                            // Connect to SSE stream for real-time updates
                            connectToImessageProgressStream();
                        } else {
                            showImessageImportStatus('error', 'Failed to start import', result.detail || 'An error occurred while starting import.');
                            imessageImportProgressContainer.style.display = 'none';
                            imessageImportInProgress = false;
                            startImessageImportBtn.disabled = false;
                            cancelImessageImportBtn.style.display = 'none';
                        }
                    } catch (error) {
                        showImessageImportStatus('error', 'Error starting import', error.message);
                        imessageImportProgressContainer.style.display = 'none';
                        imessageImportInProgress = false;
                        startImessageImportBtn.disabled = false;
                        cancelImessageImportBtn.style.display = 'none';
                    }
                });
            }

            // Cancel iMessage import
            if (cancelImessageImportBtn) {
                cancelImessageImportBtn.addEventListener('click', async () => {
                    try {
                        cancelImessageImportBtn.disabled = true;
                        showImessageImportStatus('info', 'Cancelling import...', 'Sending cancellation request...');
                        
                        const response = await fetch('/imessages/import/cancel', {
                            method: 'POST'
                        });
                        
                        const result = await response.json();
                        
                        if (result.cancelled) {
                            showImessageImportStatus('info', 'Cancellation requested', result.message || 'Import cancellation has been requested.');
                            // The SSE stream will send the cancelled event
                        } else {
                            showImessageImportStatus('info', 'No import in progress', result.message || 'No iMessage import is currently in progress.');
                            closeImessageEventSource();
                        }
                    } catch (error) {
                        showImessageImportStatus('error', 'Error cancelling import', error.message);
                    } finally {
                        cancelImessageImportBtn.disabled = false;
                    }
                });
            }

            // Check initial status on page load
            checkInitialImessageStatus();

            // WhatsApp Import Controls
            const startWhatsAppImportBtn = document.getElementById('start-whatsapp-import-btn');
            const cancelWhatsAppImportBtn = document.getElementById('cancel-whatsapp-import-btn');
            const whatsAppImportStatus = document.getElementById('whatsapp-import-status');
            const whatsAppImportStatusMessage = document.getElementById('whatsapp-import-status-message');
            const whatsAppImportStatusDetails = document.getElementById('whatsapp-import-status-details');
            const whatsAppImportProgressContainer = document.getElementById('whatsapp-import-progress-container');
            const whatsAppDirectoryPath = document.getElementById('whatsapp-import-directory');
            const whatsAppMissingAttachmentsList = document.getElementById('whatsapp-missing-attachments-list');
            const whatsAppMissingFilenames = document.getElementById('whatsapp-missing-filenames');
            let whatsAppImportInProgress = false;
            let whatsAppEventSource = null;

            // Show WhatsApp import status
            function showWhatsAppImportStatus(type, message, details = '') {
                if (!whatsAppImportStatus || !whatsAppImportStatusMessage) return;
                
                whatsAppImportStatus.style.display = 'block';
                whatsAppImportStatusMessage.textContent = message;
                whatsAppImportStatusMessage.style.color = type === 'error' ? '#dc3545' : type === 'success' ? '#28a745' : '#333';
                
                if (whatsAppImportStatusDetails) {
                    whatsAppImportStatusDetails.textContent = details;
                }
            }

            // Close WhatsApp import SSE connection
            function closeWhatsAppEventSource() {
                if (whatsAppEventSource) {
                    whatsAppEventSource.close();
                    whatsAppEventSource = null;
                }
            }

            // Connect to WhatsApp import SSE stream
            function connectToWhatsAppProgressStream() {
                // Close existing connection if any
                closeWhatsAppEventSource();

                // Create EventSource connection
                whatsAppEventSource = new EventSource('/whatsapp/import/stream');

                whatsAppEventSource.onmessage = (event) => {
                    try {
                        const eventData = JSON.parse(event.data);
                        handleWhatsAppProgressEvent(eventData);
                    } catch (error) {
                        console.error('Error parsing WhatsApp SSE event:', error);
                    }
                };

                whatsAppEventSource.onerror = (error) => {
                    console.error('WhatsApp SSE connection error:', error);
                    // Don't close on error - EventSource will attempt to reconnect
                };

                // Clean up on page unload
                window.addEventListener('beforeunload', () => {
                    closeWhatsAppEventSource();
                });
            }

            // Handle WhatsApp import progress events
            function handleWhatsAppProgressEvent(eventData) {
                const { type, data } = eventData;

                switch (type) {
                    case 'progress':
                        updateWhatsAppImportProgress(data);
                        if (data.status === 'in_progress') {
                            cancelWhatsAppImportBtn.style.display = 'inline-block';
                            startWhatsAppImportBtn.disabled = true;
                            showWhatsAppImportStatus('info', 'Import in progress...', `Processing conversation ${data.conversations_processed} of ${data.total_conversations}`);
                        }
                        break;

                    case 'completed':
                        updateWhatsAppImportProgress(data);
                        cancelWhatsAppImportBtn.style.display = 'none';
                        startWhatsAppImportBtn.disabled = false;
                        whatsAppImportInProgress = false;
                        const progressBar = document.getElementById('whatsapp-import-progress-bar');
                        const progressBarText = document.getElementById('whatsapp-progress-bar-text');
                        if (progressBar && progressBarText) {
                            progressBar.style.width = '100%';
                            progressBarText.textContent = '100%';
                        }
                        showWhatsAppImportStatus(
                            'success',
                            'Import completed successfully',
                            `Processed ${data.conversations_processed} conversation(s). ` +
                            `Imported ${data.messages_imported} message(s) ` +
                            `(${data.messages_created} created, ${data.messages_updated} updated). ` +
                            `Found ${data.attachments_found} attachment(s), ` +
                            `${data.attachments_missing} missing, ` +
                            `${data.errors} error(s).`
                        );
                        if ('Notification' in window && Notification.permission === 'granted') {
                            new Notification('WhatsApp Import Complete', {
                                body: `Imported ${data.messages_imported} messages from ${data.conversations_processed} conversations.`,
                                icon: '/static/images/expert.png'
                            });
                        }
                        closeWhatsAppEventSource();
                        break;

                    case 'error':
                        updateWhatsAppImportProgress(data);
                        cancelWhatsAppImportBtn.style.display = 'none';
                        startWhatsAppImportBtn.disabled = false;
                        whatsAppImportInProgress = false;
                        showWhatsAppImportStatus('error', 'Import error', data.error_message || 'An error occurred during import.');
                        if ('Notification' in window && Notification.permission === 'granted') {
                            new Notification('WhatsApp Import Error', {
                                body: data.error_message || 'An error occurred during import.',
                                icon: '/static/images/expert.png'
                            });
                        }
                        closeWhatsAppEventSource();
                        break;

                    case 'cancelled':
                        updateWhatsAppImportProgress(data);
                        cancelWhatsAppImportBtn.style.display = 'none';
                        startWhatsAppImportBtn.disabled = false;
                        whatsAppImportInProgress = false;
                        showWhatsAppImportStatus('info', 'Import cancelled', data.error_message || 'Import was cancelled.');
                        if ('Notification' in window && Notification.permission === 'granted') {
                            new Notification('WhatsApp Import Cancelled', {
                                body: 'Import was cancelled by user.',
                                icon: '/static/images/expert.png'
                            });
                        }
                        closeWhatsAppEventSource();
                        break;

                    case 'heartbeat':
                        // Keep connection alive - no UI update needed
                        break;

                    default:
                        console.log('Unknown WhatsApp event type:', type);
                }
            }

            // Update WhatsApp import progress
            function updateWhatsAppImportProgress(stats) {
                if (!whatsAppImportProgressContainer) return;
                
                whatsAppImportProgressContainer.style.display = 'block';
                
                const currentConversationName = document.getElementById('whatsapp-current-conversation-name');
                const whatsAppProgressText = document.getElementById('whatsapp-conversation-progress-text');
                const whatsAppImportProgressBar = document.getElementById('whatsapp-import-progress-bar');
                const whatsAppProgressBarText = document.getElementById('whatsapp-progress-bar-text');
                const whatsAppMessagesImported = document.getElementById('whatsapp-messages-imported-count');
                const whatsAppMessagesCreated = document.getElementById('whatsapp-messages-created-count');
                const whatsAppMessagesUpdated = document.getElementById('whatsapp-messages-updated-count');
                const whatsAppAttachmentsFound = document.getElementById('whatsapp-attachments-found-count');
                const whatsAppAttachmentsMissing = document.getElementById('whatsapp-attachments-missing-count');
                const whatsAppErrors = document.getElementById('whatsapp-errors-count');

                if (currentConversationName) {
                    currentConversationName.textContent = stats.current_conversation || '-';
                }

                if (whatsAppProgressText && stats.total_conversations > 0) {
                    whatsAppProgressText.textContent = `${stats.conversations_processed} / ${stats.total_conversations}`;
                }

                if (whatsAppImportProgressBar && whatsAppProgressBarText && stats.total_conversations > 0) {
                    const percentage = Math.round((stats.conversations_processed / stats.total_conversations) * 100);
                    whatsAppImportProgressBar.style.width = `${percentage}%`;
                    whatsAppProgressBarText.textContent = `${percentage}%`;
                }

                if (whatsAppMessagesImported) {
                    whatsAppMessagesImported.textContent = stats.messages_imported || 0;
                }
                if (whatsAppMessagesCreated) {
                    whatsAppMessagesCreated.textContent = stats.messages_created || 0;
                }
                if (whatsAppMessagesUpdated) {
                    whatsAppMessagesUpdated.textContent = stats.messages_updated || 0;
                }
                if (whatsAppAttachmentsFound) {
                    whatsAppAttachmentsFound.textContent = stats.attachments_found || 0;
                }
                if (whatsAppAttachmentsMissing) {
                    whatsAppAttachmentsMissing.textContent = stats.attachments_missing || 0;
                }
                if (whatsAppErrors) {
                    whatsAppErrors.textContent = stats.errors || 0;
                }

                // Update missing attachment filenames
                if (stats.missing_attachment_filenames && stats.missing_attachment_filenames.length > 0) {
                    if (whatsAppMissingAttachmentsList) {
                        whatsAppMissingAttachmentsList.style.display = 'block';
                    }
                    if (whatsAppMissingFilenames) {
                        whatsAppMissingFilenames.innerHTML = stats.missing_attachment_filenames
                            .map(filename => `<div style="margin-bottom: 4px;">${filename}</div>`)
                            .join('');
                    }
                } else {
                    if (whatsAppMissingAttachmentsList) {
                        whatsAppMissingAttachmentsList.style.display = 'none';
                    }
                }
            }

            // Check initial WhatsApp import status
            async function checkInitialWhatsAppStatus() {
                if (!whatsAppImportStatus) return;
                
                try {
                    const response = await fetch('/whatsapp/import/status');
                    if (!response.ok) {
                        return;
                    }
                    const status = await response.json();
                    
                    if (status.in_progress) {
                        cancelWhatsAppImportBtn.style.display = 'inline-block';
                        startWhatsAppImportBtn.disabled = true;
                        whatsAppImportInProgress = true;
                        // Connect to stream to get updates
                        connectToWhatsAppProgressStream();
                        updateWhatsAppImportProgress(status);
                    } else {
                        cancelWhatsAppImportBtn.style.display = 'none';
                        startWhatsAppImportBtn.disabled = false;
                        whatsAppImportInProgress = false;
                    }
                } catch (error) {
                    console.error('Error checking initial WhatsApp import status:', error);
                }
            }

            // Start WhatsApp import
            if (startWhatsAppImportBtn) {
                startWhatsAppImportBtn.addEventListener('click', async () => {
                    const directoryPath = whatsAppDirectoryPath?.value?.trim();
                    
                    if (!directoryPath) {
                        showWhatsAppImportStatus('error', 'Directory path required', 'Please enter a directory path.');
                        return;
                    }
                    
                    if (whatsAppImportInProgress) {
                        showWhatsAppImportStatus('error', 'Import already in progress', 'Please wait for the current import to complete.');
                        return;
                    }
                    
                    try {
                        whatsAppImportInProgress = true;
                        startWhatsAppImportBtn.disabled = true;
                        cancelWhatsAppImportBtn.style.display = 'inline-block';
                        showWhatsAppImportStatus('info', 'Starting import...', 'Sending request to server...');
                        
                        // Clear previous missing filenames
                        if (whatsAppMissingFilenames) {
                            whatsAppMissingFilenames.innerHTML = '';
                        }
                        if (whatsAppMissingAttachmentsList) {
                            whatsAppMissingAttachmentsList.style.display = 'none';
                        }
                        
                        updateWhatsAppImportProgress({
                            conversations_processed: 0,
                            total_conversations: 0,
                            messages_imported: 0,
                            messages_created: 0,
                            messages_updated: 0,
                            attachments_found: 0,
                            attachments_missing: 0,
                            missing_attachment_filenames: [],
                            errors: 0
                        });
                        
                        const response = await fetch('/whatsapp/import', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({
                                directory_path: directoryPath
                            })
                        });
                        
                        const result = await response.json();
                        
                        if (response.ok) {
                            showWhatsAppImportStatus('info', 'Import started', result.message || 'WhatsApp import has been initiated.');
                            
                            // Connect to SSE stream for real-time updates
                            connectToWhatsAppProgressStream();
                        } else {
                            showWhatsAppImportStatus('error', 'Failed to start import', result.detail || 'An error occurred while starting import.');
                            whatsAppImportProgressContainer.style.display = 'none';
                            whatsAppImportInProgress = false;
                            startWhatsAppImportBtn.disabled = false;
                            cancelWhatsAppImportBtn.style.display = 'none';
                        }
                    } catch (error) {
                        showWhatsAppImportStatus('error', 'Error starting import', error.message);
                        whatsAppImportProgressContainer.style.display = 'none';
                        whatsAppImportInProgress = false;
                        startWhatsAppImportBtn.disabled = false;
                        cancelWhatsAppImportBtn.style.display = 'none';
                    }
                });
            }

            // Cancel WhatsApp import
            if (cancelWhatsAppImportBtn) {
                cancelWhatsAppImportBtn.addEventListener('click', async () => {
                    try {
                        cancelWhatsAppImportBtn.disabled = true;
                        showWhatsAppImportStatus('info', 'Cancelling import...', 'Sending cancellation request...');
                        
                        const response = await fetch('/whatsapp/import/cancel', {
                            method: 'POST'
                        });
                        
                        const result = await response.json();
                        
                        if (result.cancelled) {
                            showWhatsAppImportStatus('info', 'Cancellation requested', result.message || 'Import cancellation has been requested.');
                            // The SSE stream will send the cancelled event
                        } else {
                            showWhatsAppImportStatus('info', 'No import in progress', result.message || 'No WhatsApp import is currently in progress.');
                            closeWhatsAppEventSource();
                        }
                    } catch (error) {
                        showWhatsAppImportStatus('error', 'Error cancelling import', error.message);
                    } finally {
                        cancelWhatsAppImportBtn.disabled = false;
                    }
                });
            }

            // Check initial status on page load
            checkInitialWhatsAppStatus();

            // Sidebar button event listeners
            if (DOM.fbAlbumsSidebarBtn) {
                DOM.fbAlbumsSidebarBtn.addEventListener('click', () => {
                    Modals.FBAlbums.open();
                });
            }

            if (DOM.imageGallerySidebarBtn) {
                DOM.imageGallerySidebarBtn.addEventListener('click', () => {
                    Modals.ImageGallery.open();
                });
            }

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

            if (DOM.haveYourSaySidebarBtn) {
                DOM.haveYourSaySidebarBtn.addEventListener('click', () => {
                    Modals.HaveYourSay.open();
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
            Config.init(); // Loads and applies settings, sets up its listeners
            Chat.renderExistingMessages();
            VoiceSelector.init(); // Sets initial voice state, creativity lock, listeners
            Modals.initAll();
            SSE.init();
            InterviewerMode.init(); // Initialize interviewer mode
            initEventListeners(); // Attach main app event listeners

            // Test interviewer mode button
            if (DOM.interviewerModeBtn) {
                console.log('Testing interviewer mode button...');
                DOM.interviewerModeBtn.addEventListener('click', async () => {
                    console.log('Interviewer mode button clicked from main init!');
                });
            }

            // Initial info box visibility
            if (DOM.chatBox.querySelectorAll('.message').length === 0 && DOM.infoBox) {
                DOM.infoBox.classList.remove('hidden');
                if (!DOM.chatBox.contains(DOM.infoBox)) DOM.chatBox.appendChild(DOM.infoBox);
            } else if (DOM.infoBox) {
                DOM.infoBox.classList.add('hidden');
            }
             window.onbeforeunload = () => { SSE.close(); };
        }
        return { init, processFormSubmit, handleNewChat };
    })();

    App.init();

});



