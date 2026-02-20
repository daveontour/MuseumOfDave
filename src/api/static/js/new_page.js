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
        // FUNCTION_NAMES: Object.freeze({
        //     FirstFunction: "testFunction",
        //     SecondFunction: "showFBMessengerOptions",
        //     ThirdFunction: "showFBAlbumsOptions",
        //     FourthFunction: "openGeoModal",
        //     FifthFunction: "showLocationInfo",
        //     SixthFunction: "showImageGallery",
        //     SeventhFunction: "testEmail",
        //     EighthFunction: "showEmailGallery"
        // }),
        VOICE_DESCRIPTIONS: {
            'expert': 'a knowledgeable expert who provides accurate, factual information',
            'psychologist': 'a compassionate therapist offering psychological insights',
            'after_death': 'an uptight British professor',
            'secret_admirer': 'a romantic soul expressing deep affection who is very shy and reserved and remained annonymous',
            'bar_girl': 'a friendly Thai bar girl called Lucky offering conversation and advice',
            'parents': 'caring parental figures providing guidance and support',
            'preacher': 'a spiritual advisor who is extremely pious and judgemental',
            'dave': '{SUBJECT_NAME} in their own voice',
            'irish': 'a cheerful Irish comedian who is very funny and has a great sense of humour and responds in limmericks',
            'haiku': 'a poetic soul who responds in haiku form',
            'insult': 'a comedic roaster delivering playful burns',
            'earthchild': 'a free spirit sharing natural wisdom',
            'female_friend': 'a supportive female friend offering caring advice',
            'male_friend': 'a supportive male friend offering caring advice'
        },
        API_PATHS: {
            CHAT: '/chat/generate',
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
        fbAlbumsList: document.getElementById('fb-albums-list'),
        fbAlbumsSearch: document.getElementById('fb-albums-search'),
        fbAlbumsMasterPane: document.getElementById('fb-albums-master-pane'),
        fbAlbumsSlavePane: document.getElementById('fb-albums-slave-pane'),
        fbAlbumsResizeHandle: document.getElementById('fb-albums-resize-handle'),
        fbAlbumsAlbumTitle: document.getElementById('fb-albums-album-title'),
        fbAlbumsAlbumDescription: document.getElementById('fb-albums-album-description'),
        fbAlbumsImagesContainer: document.getElementById('fb-albums-images-container'),
        closeFBAlbumsModalBtn: document.getElementById('close-fb-albums-modal'),
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
        // Reference Documents elements
        referenceDocumentsModal: document.getElementById('reference-documents-modal'),
        closeReferenceDocumentsModalBtn: document.getElementById('close-reference-documents-modal'),
        relationshipsModal: document.getElementById('relationships-modal'),
        closeRelationshipsModalBtn: document.getElementById('close-relationships-modal'),
        contactsModal: document.getElementById('contacts-modal'),
        closeContactsModalBtn: document.getElementById('close-contacts-modal'),
        extractContactsBtn: document.getElementById('extract-contacts-btn'),
        contactsLoading: document.getElementById('contacts-loading'),
        contactsTableContainer: document.getElementById('contacts-table-container'),
        contactsTableBody: document.getElementById('contacts-table-body'),
        referenceDocumentsList: document.getElementById('reference-documents-list'),
        referenceDocumentsSearch: document.getElementById('reference-documents-search'),
        referenceDocumentsCategoryFilter: document.getElementById('reference-documents-category-filter'),
        referenceDocumentsContentTypeFilter: document.getElementById('reference-documents-content-type-filter'),
        referenceDocumentsTaskFilter: document.getElementById('reference-documents-task-filter'),
        referenceDocumentsUploadBtn: document.getElementById('reference-documents-upload-btn'),
        referenceDocumentsUploadModal: document.getElementById('reference-documents-upload-modal'),
        closeReferenceDocumentsUploadModalBtn: document.getElementById('close-reference-documents-upload-modal'),
        referenceDocumentsUploadForm: document.getElementById('reference-documents-upload-form'),
        referenceDocumentsUploadCancelBtn: document.getElementById('reference-documents-upload-cancel'),
        referenceDocumentsEditModal: document.getElementById('reference-documents-edit-modal'),
        closeReferenceDocumentsEditModalBtn: document.getElementById('close-reference-documents-edit-modal'),
        referenceDocumentsEditForm: document.getElementById('reference-documents-edit-form'),
        referenceDocumentsEditCancelBtn: document.getElementById('reference-documents-edit-cancel'),
        referenceDocumentsSidebarBtn: document.getElementById('reference-documents-sidebar-btn'),
        referenceDocumentsNotificationModal: document.getElementById('reference-documents-notification-modal'),
        closeReferenceDocumentsNotificationModalBtn: document.getElementById('close-reference-documents-notification-modal'),
        referenceDocumentsNotificationList: document.getElementById('reference-documents-notification-list'),
        referenceDocumentsNotificationCancelBtn: document.getElementById('reference-documents-notification-cancel'),
        referenceDocumentsNotificationProceedBtn: document.getElementById('reference-documents-notification-proceed'),
        // Conversation management elements
        conversationListModal: document.getElementById('conversation-list-modal'),
        closeConversationListModalBtn: document.getElementById('close-conversation-list-modal'),
        conversationListContainer: document.getElementById('conversation-list-container'),
        newConversationBtn: document.getElementById('new-conversation-btn'),
        resumeConversationBtn: document.getElementById('resume-conversation-btn'),
        conversationIndicator: document.getElementById('conversation-indicator'),
        newConversationModal: document.getElementById('new-conversation-modal'),
        // Subject Configuration Modal elements
        subjectConfigurationModal: document.getElementById('subject-configuration-modal'),
        closeSubjectConfigModalBtn: document.getElementById('close-subject-config-modal'),
        subjectNameInput: document.getElementById('subject-name-input'),
        subjectGenderSelect: document.getElementById('subject-gender-select'),
        familyNameInput: document.getElementById('family-name-input'),
        otherNamesInput: document.getElementById('other-names-input'),
        emailAddressesInput: document.getElementById('email-addresses-input'),
        phoneNumbersInput: document.getElementById('phone-numbers-input'),
        whatsappHandleInput: document.getElementById('whatsapp-handle-input'),
        instagramHandleInput: document.getElementById('instagram-handle-input'),
        requestWritingStyleBtn: document.getElementById('request-writing-style-btn'),
        writingStyleLoading: document.getElementById('writing-style-loading'),
        writingStyleDisplay: document.getElementById('writing-style-display'),
        systemInstructionsTextarea: document.getElementById('system-instructions-textarea'),
        coreSystemInstructionsTextarea: document.getElementById('core-system-instructions-textarea'),
        subjectConfigTabs: document.querySelectorAll('.subject-config-tab'),
        saveSubjectConfigBtn: document.getElementById('save-subject-config-btn'),
        cancelSubjectConfigBtn: document.getElementById('cancel-subject-config-btn'),
        closeNewConversationModalBtn: document.getElementById('close-new-conversation-modal'),
        newConversationTitleInput: document.getElementById('new-conversation-title-input'),
        newConversationVoiceSelect: document.getElementById('new-conversation-voice-select'),
        createConversationBtn: document.getElementById('create-conversation-btn'),
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
        refreshLocationsBtn: document.getElementById('refresh-locations-btn'),
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
        downloadImageGalleryBtn: document.getElementById('download-image-gallery-btn'),
        // Email Gallery Modal Elements
        emailGalleryModal: document.getElementById('email-gallery-modal'),
        closeEmailGalleryModalBtn: document.getElementById('close-email-gallery-modal'),
        emailGalleryList: document.getElementById('email-gallery-list'),
        emailGalleryMasterPane: document.querySelector('.email-gallery-master-pane'),
        emailGalleryDivider: document.getElementById('email-gallery-divider'),
        emailGalleryDetailPane: document.querySelector('.email-gallery-detail-pane'),
        emailGalleryInstructions: document.getElementById('email-gallery-instructions'),
        emailGalleryEmailContent: document.getElementById('email-gallery-email-content'),
        emailGalleryIframe: document.getElementById('email-gallery-iframe'),
        emailGalleryAttachmentsGrid: document.getElementById('email-gallery-attachments-grid'),
        emailGallerySearch: document.getElementById('email-gallery-search'),
        emailGallerySender: document.getElementById('email-gallery-sender'),
        emailGalleryRecipient: document.getElementById('email-gallery-recipient'),
        emailGalleryToFrom: document.getElementById('email-gallery-to-from'),
        emailGalleryYearFilter: document.getElementById('email-gallery-year-filter'),
        emailGalleryMonthFilter: document.getElementById('email-gallery-month-filter'),
        emailGalleryAttachmentsFilter: document.getElementById('email-gallery-attachments-filter'),
        emailGalleryFolderFilter: document.getElementById('email-gallery-folder-filter'),
        emailGallerySearchBtn: document.getElementById('email-gallery-search-btn'),
        emailGalleryClearBtn: document.getElementById('email-gallery-clear-btn'),
        emailGalleryViewToggle: document.getElementById('email-gallery-view-toggle'),
        emailGalleryMetadataSubject: document.getElementById('email-gallery-metadata-subject'),
        emailGalleryMetadataFrom: document.getElementById('email-gallery-metadata-from'),
        emailGalleryMetadataDate: document.getElementById('email-gallery-metadata-date'),
        emailGalleryMetadataFolder: document.getElementById('email-gallery-metadata-folder'),
        emailGalleryEmailDetails: null, // Removed from HTML, kept for compatibility
        emailAskAIBtn: document.getElementById('email-ask-ai-btn'),
        emailDeleteBtn: document.getElementById('email-delete-btn'),
        emailAskAIModal: document.getElementById('email-ask-ai-modal'),
        // Attachment Modals
        emailAttachmentImageModal: document.getElementById('email-attachment-image-modal'),
        emailAttachmentDocumentModal: document.getElementById('email-attachment-document-modal'),
        closeEmailAttachmentImageModal: document.getElementById('close-email-attachment-image-modal'),
        closeEmailAttachmentDocumentModal: document.getElementById('close-email-attachment-document-modal'),
        emailAttachmentImageDisplay: document.getElementById('email-attachment-image-display'),
        emailAttachmentDocumentIframe: document.getElementById('email-attachment-document-iframe'),
        // Email Gallery Button
        emailGalleryBtn: document.getElementById('email-gallery-btn'),
        // Email Editor Modal Elements
        emailEditorModal: document.getElementById('email-editor-modal'),
        closeEmailEditorModalBtn: document.getElementById('close-email-editor-modal'),
        emailEditorSearch: document.getElementById('email-editor-search'),
        emailEditorSender: document.getElementById('email-editor-sender'),
        emailEditorRecipient: document.getElementById('email-editor-recipient'),
        emailEditorToFrom: document.getElementById('email-editor-to-from'),
        emailEditorYearFilter: document.getElementById('email-editor-year-filter'),
        emailEditorMonthFilter: document.getElementById('email-editor-month-filter'),
        emailEditorAttachmentsFilter: document.getElementById('email-editor-attachments-filter'),
        emailEditorSearchBtn: document.getElementById('email-editor-search-btn'),
        emailEditorClearBtn: document.getElementById('email-editor-clear-btn'),
        emailEditorTableBody: document.getElementById('email-editor-table-body'),
        emailEditorPagination: document.getElementById('email-editor-pagination'),
        emailEditorSidebarBtn: document.getElementById('email-editor-sidebar-btn'),
        emailEditorBulkDeleteBtn: document.getElementById('email-editor-bulk-delete-btn'),
        // New Image Gallery Elements
        newImageGalleryModal: document.getElementById('new-image-gallery-modal'),
        closeNewImageGalleryModalBtn: document.getElementById('close-new-image-gallery-modal'),
        newImageGalleryTitle: document.getElementById('new-image-gallery-title'),
        newImageGalleryDescription: document.getElementById('new-image-gallery-description'),
        newImageGalleryTags: document.getElementById('new-image-gallery-tags'),
        newImageGalleryAuthor: document.getElementById('new-image-gallery-author'),
        newImageGallerySource: document.getElementById('new-image-gallery-source'),
        newImageGalleryYearFilter: document.getElementById('new-image-gallery-year-filter'),
        newImageGalleryMonthFilter: document.getElementById('new-image-gallery-month-filter'),
        newImageGalleryRating: document.getElementById('new-image-gallery-rating'),
        newImageGalleryRatingMin: document.getElementById('new-image-gallery-rating-min'),
        newImageGalleryRatingMax: document.getElementById('new-image-gallery-rating-max'),
        newImageGalleryHasGps: document.getElementById('new-image-gallery-has-gps'),
        newImageGalleryProcessed: document.getElementById('new-image-gallery-processed'),
        newImageGallerySearchBtn: document.getElementById('new-image-gallery-search-btn'),
        newImageGalleryClearBtn: document.getElementById('new-image-gallery-clear-btn'),
        newImageGalleryThumbnailGrid: document.getElementById('new-image-gallery-thumbnail-grid'),
        newImageGalleryMasterPane: document.querySelector('.new-image-gallery-master-pane'),
        newImageGallerySelectMode: document.getElementById('new-image-gallery-select-mode'),
        newImageGalleryBulkEditSection: document.getElementById('new-image-gallery-bulk-edit-section'),
        newImageGallerySelectedCount: document.getElementById('new-image-gallery-selected-count'),
        newImageGalleryBulkTags: document.getElementById('new-image-gallery-bulk-tags'),
        newImageGalleryApplyTagsBtn: document.getElementById('new-image-gallery-apply-tags-btn'),
        newImageGalleryDeleteSelectedBtn: document.getElementById('new-image-gallery-delete-selected-btn'),
        newImageGalleryClearSelectionBtn: document.getElementById('new-image-gallery-clear-selection-btn'),
        // New Image Gallery Detail Modal Elements
        newImageGalleryDetailModal: document.getElementById('new-image-gallery-detail-modal'),
        closeNewImageGalleryDetailModalBtn: document.getElementById('close-new-image-gallery-detail-modal'),
        newImageGalleryDetailImage: document.getElementById('new-image-gallery-detail-image'),
        newImageDetailTitle: document.getElementById('new-image-detail-title'),
        newImageDetailDescription: document.getElementById('new-image-detail-description'),
        newImageDetailDescriptionEdit: document.getElementById('new-image-detail-description-edit'),
        newImageDetailAuthor: document.getElementById('new-image-detail-author'),
        newImageDetailTags: document.getElementById('new-image-detail-tags'),
        newImageDetailTagsEdit: document.getElementById('new-image-detail-tags-edit'),
        newImageDetailCategories: document.getElementById('new-image-detail-categories'),
        newImageDetailNotes: document.getElementById('new-image-detail-notes'),
        newImageDetailDate: document.getElementById('new-image-detail-date'),
        newImageDetailRating: document.getElementById('new-image-detail-rating'),
        newImageDetailRatingContainer: document.getElementById('new-image-detail-rating-container'),
        newImageDetailRatingEdit: document.getElementById('new-image-detail-rating-edit'),
        newImageGallerySaveBtn: document.getElementById('new-image-gallery-save-btn'),
        newImageDetailImageType: document.getElementById('new-image-detail-image-type'),
        newImageDetailSource: document.getElementById('new-image-detail-source'),
        newImageDetailSourceReference: document.getElementById('new-image-detail-source-reference'),
        newImageDetailRegion: document.getElementById('new-image-detail-region'),
        newImageDetailGpsRow: document.getElementById('new-image-detail-gps-row'),
        newImageDetailGps: document.getElementById('new-image-detail-gps'),
        newImageDetailAltitudeRow: document.getElementById('new-image-detail-altitude-row'),
        newImageDetailAltitude: document.getElementById('new-image-detail-altitude'),
        newImageDetailAvailableForTask: document.getElementById('new-image-detail-available-for-task'),
        newImageDetailProcessed: document.getElementById('new-image-detail-processed'),
        newImageDetailLocationProcessed: document.getElementById('new-image-detail-location-processed'),
        newImageDetailImageProcessed: document.getElementById('new-image-detail-image-processed'),
        newImageDetailCreatedAt: document.getElementById('new-image-detail-created-at'),
        newImageDetailUpdatedAt: document.getElementById('new-image-detail-updated-at'),
        newImageGalleryDeleteBtn: document.getElementById('new-image-gallery-delete-btn'),
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
        //imageGallerySidebarBtn: document.getElementById('image-gallery-sidebar-btn'),
        locationsSidebarBtn: document.getElementById('locations-sidebar-btn'),
        emailGallerySidebarBtn: document.getElementById('email-gallery-sidebar-btn'),
        newImageGallerySidebarBtn: document.getElementById('new-image-gallery-sidebar-btn'),
        suggestionsSidebarBtn: document.getElementById('suggestions-sidebar-btn'),
       // haveYourSaySidebarBtn: document.getElementById('have-your-say-sidebar-btn'),
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
    };

    // Debug DOM elements

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

                let selector = selectedVoice + '_sm';
                let imgSrc = `/static/images/${CONSTANTS.VOICE_IMAGES[selector]}`;
                voiceImageSmall.src = imgSrc;
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

            //The browser_action is a json object that is included in the embeddedJson. It is used to tell the browser to perform an action.
            //The browser_action object has a functionName property that is the name of the function to perform.
            //The browser_action object has an args property that is an array of arguments for the function.
            // The AI may include a browser_action object in the embeddedJson to tell the browser to perform an action.
            // The AI is told about the available browser actions in the system_instructions_chat.txt file.
            if (role === 'assistant') {
                console.log('embeddedJson', embeddedJson);
                if (embeddedJson && embeddedJson.browser_action) {
                    _processBrowserActions(embeddedJson.browser_action);
                }
            }
            
            return messageElement;
        }

        // The browser_action is a json object that is included in the embeddedJson. It is used to tell the browser to perform an action.
        function _processBrowserActions(browser_action) {
            if (browser_action) {
                console.log('browser_action', browser_action);
            } else {
                console.log('no browser_actions');
                return;
            }
            switch (browser_action.functionName) {
                case 'showAlert':
                    alert(browser_action.args[0]);
                    break;
                case 'changeBackgroundColor':
                    document.body.style.backgroundColor = browser_action.args[0];
                    break;
                case 'showContactEmailGallery':
                    Modals.EmailGallery.openContact(browser_action.args[0]);
                    break;
                case 'showFacebookAlbums':
                    Modals.FBAlbums.open();
                    break;
                case 'showImageGallery':
                    Modals.NewImageGallery.open();
                    break;
                case 'showTaggedImages':
                    Modals.NewImageGallery.openTaggedImages(browser_action.args[0]);
                    break;
                case 'showImagesFromDate':
                    Modals.NewImageGallery.openImagesFromDate(browser_action.args[0], browser_action.args[1]);
                    break;
                case 'showLocationInfo':
                    Modals.Locations.openMapView();
                    break;
                default:
                    console.log('unknown browser_action', browser_action);
                    break;
            }
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
            // Re-query DOM elements to ensure we have fresh references
            const voicePreviewImg = document.querySelector('.preview-image');
            const voicePreviewDesc = document.querySelector('.preview-description');
            
            if (voicePreviewImg) {
                const imageName = CONSTANTS.VOICE_IMAGES[voiceName];
 
                if (imageName) {
                    const imagePath = `/static/images/${imageName}`;
                    voicePreviewImg.src = imagePath;
                    voicePreviewImg.alt = `${voiceName} character`;
                    

                    voicePreviewImg.onerror = () => {
                        console.error('Failed to load voice preview image:', imagePath);
                    };
                } else {
                    console.warn(`Voice image not found for: ${voiceName}`);
                }
            } else {
                console.error('voicePreviewImg element not found!');
            }
            
            if (voicePreviewDesc) {
                let description = CONSTANTS.VOICE_DESCRIPTIONS[voiceName] || '';
                
                // Try to get description from voice icon wrapper's data-description attribute first
                const voiceWrapper = document.querySelector(`.voice-icon-wrapper[data-voice="${voiceName}"]`);
                if (voiceWrapper && voiceWrapper.dataset.description) {
                    description = voiceWrapper.dataset.description;
                }
                
                // Replace subject name placeholders if subject name is available
                if (Modals && Modals.SubjectConfiguration && Modals.SubjectConfiguration.getSubjectName) {
                    const subjectName = Modals.SubjectConfiguration.getSubjectName();
                    if (subjectName) {
                        description = description.replace(/Dave/g, subjectName);
                        description = description.replace(/Dave's/g, `${subjectName}'s`);
                        description = description.replace(/{SUBJECT_NAME}/g, subjectName);
                    }
                }
                
                voicePreviewDesc.textContent = description;
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
            
            // Re-query voiceIconWrappers to ensure we have fresh references (in case DOM was updated)
            const voiceIconWrappers = document.querySelectorAll('.voice-icon-wrapper');
            
            voiceIconWrappers.forEach(wrapper => {
                const wrapperVoice = wrapper.dataset.voice;
                const img = wrapper.querySelector('.voice-icon');
                if (img) {
                    if(wrapperVoice === selectedVoice) {
                        // Add 'selected' class for highlighting
                        img.classList.add('selected');
                    } else {
                        // Remove 'selected' class
                        img.classList.remove('selected');
                    }
                }
            });
        }
        
        function setInitialState() {
            const initialVoice = getSelectedVoice();
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

        function setVoice(voiceName) {
            if (!voiceName) return;
            
            if (DOM.voiceSelect) {
                DOM.voiceSelect.value = voiceName;
                // Manually dispatch change event to trigger all handlers
                DOM.voiceSelect.dispatchEvent(new Event('change', { bubbles: true }));
                highlightSelectedVoiceIcon(); // Update highlight
            }
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
        return { init, getSelectedVoice, setVoice, updateLoadingIndicatorImage, updateVoicePreview, updateSelectedVoiceImage };
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
            function close() {
                const modal = document.getElementById('sms-messages-modal');
                if (modal) {
                    modal.style.display = 'none';
                }
            }

            return { init, open, close };
        })(),

        FBAlbums: (() => {
            let albums = [];
            let filteredAlbums = [];
            let selectedAlbumId = null;
            let resizeStartX = null;
            let resizeStartWidth = null;

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
                    const seconds = String(date.getSeconds()).padStart(2, '0');
                    
                    return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
                } catch (error) {
                    return 'Invalid Date';
                }
            }

            async function loadAlbums() {
                if (!DOM.fbAlbumsList) return;
                
                DOM.fbAlbumsList.innerHTML = '<div style="text-align: center; padding: 2rem; color: #666;">Loading albums...</div>';
                
                try {
                    const response = await fetch('/facebook/albums');
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    albums = await response.json();
                    filteredAlbums = albums;
                    renderAlbums();
                } catch (error) {
                    console.error("Failed to load FB albums:", error);
                    DOM.fbAlbumsList.innerHTML = '<div style="text-align: center; padding: 2rem; color: #dc3545;">Failed to load albums: ' + error.message + '</div>';
                }
            }

            function renderAlbums() {
                if (!DOM.fbAlbumsList) return;
                
                if (filteredAlbums.length === 0) {
                    DOM.fbAlbumsList.innerHTML = '<div style="text-align: center; padding: 2rem; color: #666;">No albums found</div>';
                    return;
                }
                
                DOM.fbAlbumsList.innerHTML = '';
                
                filteredAlbums.forEach(album => {
                    const albumItem = document.createElement('div');
                    albumItem.className = 'fb-album-item';
                    albumItem.style.cssText = 'padding: 12px; margin-bottom: 8px; border-radius: 6px; cursor: pointer; transition: background-color 0.2s; border: 1px solid transparent;';
                    albumItem.style.backgroundColor = selectedAlbumId === album.id ? '#e3f2fd' : 'transparent';
                    albumItem.style.borderColor = selectedAlbumId === album.id ? '#2196F3' : 'transparent';
                    
                    albumItem.onmouseover = () => {
                        if (selectedAlbumId !== album.id) {
                            albumItem.style.backgroundColor = '#f0f0f0';
                        }
                    };
                    albumItem.onmouseout = () => {
                        if (selectedAlbumId !== album.id) {
                            albumItem.style.backgroundColor = 'transparent';
                        }
                    };
                    
                    albumItem.onclick = () => selectAlbum(album.id);
                    
                    const title = document.createElement('div');
                    title.style.cssText = 'font-weight: 600; color: #233366; margin-bottom: 4px; font-size: 14px;';
                    title.textContent = album.name;
                    
                    const meta = document.createElement('div');
                    meta.style.cssText = 'font-size: 12px; color: #666;';
                    meta.textContent = `${album.image_count || 0} image${album.image_count !== 1 ? 's' : ''}`;
                    
                    albumItem.appendChild(title);
                    albumItem.appendChild(meta);
                    DOM.fbAlbumsList.appendChild(albumItem);
                });
            }

            async function selectAlbum(albumId) {
                selectedAlbumId = albumId;
                renderAlbums();
                
                const album = albums.find(a => a.id === albumId);
                if (!album) return;
                
                // Update header
                if (DOM.fbAlbumsAlbumTitle) {
                    DOM.fbAlbumsAlbumTitle.textContent = album.name;
                }
                if (DOM.fbAlbumsAlbumDescription) {
                    DOM.fbAlbumsAlbumDescription.textContent = album.description || '';
                }
                
                // Load images
                if (!DOM.fbAlbumsImagesContainer) return;
                
                DOM.fbAlbumsImagesContainer.innerHTML = '<div style="text-align: center; padding: 2rem; color: #666; grid-column: 1 / -1;">Loading images...</div>';
                
                try {
                    const response = await fetch(`/facebook/albums/${albumId}/images`);
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    const images = await response.json();
                    
                    if (images.length === 0) {
                        DOM.fbAlbumsImagesContainer.innerHTML = '<div style="text-align: center; padding: 2rem; color: #666; grid-column: 1 / -1;">No images in this album</div>';
                        return;
                    }
                    
                    DOM.fbAlbumsImagesContainer.innerHTML = '';
                    
                    images.forEach(image => {
                        const imageCard = document.createElement('div');
                        imageCard.style.cssText = 'position: relative; border-radius: 8px; overflow: hidden; background: #f8f9fa; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; min-height: 200px;';
                        imageCard.onmouseover = () => {
                            imageCard.style.transform = 'scale(1.02)';
                            imageCard.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
                        };
                        imageCard.onmouseout = () => {
                            imageCard.style.transform = 'scale(1)';
                            imageCard.style.boxShadow = 'none';
                        };
                        
                        const img = document.createElement('img');
                        img.src = `/facebook/albums/images/${image.id}`;
                        img.alt = image.title || image.filename || 'Album image';
                        img.style.cssText = 'width: 100%; height: 200px; min-height: 200px; object-fit: cover; display: block;';
                        img.loading = 'lazy';
                        
                        imageCard.onclick = () => {
                            // Open full image in modal
                            if (DOM.singleImageModal && DOM.singleImageModalImg) {
                                // Hide other media elements
                                if (DOM.singleImageModalAudio) DOM.singleImageModalAudio.style.display = 'none';
                                if (DOM.singleImageModalVideo) DOM.singleImageModalVideo.style.display = 'none';
                                if (DOM.singleImageModalPdf) DOM.singleImageModalPdf.style.display = 'none';
                                
                                // Show and set image
                                DOM.singleImageModalImg.src = img.src;
                                DOM.singleImageModalImg.alt = img.alt;
                                DOM.singleImageModalImg.style.display = 'block';
                                
                                // Set image details if available
                                if (DOM.singleImageDetails) {
                                    const details = [];
                                    if (image.title) details.push(`<strong>Title:</strong> ${image.title}`);
                                    if (image.description) details.push(`<strong>Description:</strong> ${image.description}`);
                                    if (image.filename) details.push(`<strong>Filename:</strong> ${image.filename}`);
                                    if (image.creation_timestamp) details.push(`<strong>Date:</strong> ${formatDateAustralian(image.creation_timestamp)}`);
                                    DOM.singleImageDetails.innerHTML = details.length > 0 ? details.join('<br>') : '';
                                }
                                
                                // Open modal
                                Modals._openModal(DOM.singleImageModal);
                            }
                        };
                        
                        // Show overlay with image description if available, otherwise album title
                        // Priority: image.description > image.title > album.name
                        const overlayText = image.description || image.title || album.name;
                        const overlay = document.createElement('div');
                        overlay.style.cssText = 'position: absolute; bottom: 0; left: 0; right: 0; background: linear-gradient(to top, rgba(0,0,0,0.7), transparent); padding: 8px; color: white; font-size: 12px;';
                        overlay.textContent = overlayText;
                        imageCard.appendChild(overlay);
                        
                        imageCard.appendChild(img);
                        DOM.fbAlbumsImagesContainer.appendChild(imageCard);
                    });
                } catch (error) {
                    console.error("Failed to load album images:", error);
                    DOM.fbAlbumsImagesContainer.innerHTML = '<div style="text-align: center; padding: 2rem; color: #dc3545; grid-column: 1 / -1;">Failed to load images: ' + error.message + '</div>';
                }
            }

            function searchAlbums(query) {
                const searchTerm = query.toLowerCase().trim();
                if (!searchTerm) {
                    filteredAlbums = albums;
                } else {
                    filteredAlbums = albums.filter(album => 
                        album.name.toLowerCase().includes(searchTerm) ||
                        (album.description && album.description.toLowerCase().includes(searchTerm))
                    );
                }
                renderAlbums();
            }

            function startResize(e) {
                e.preventDefault();
                resizeStartX = e.clientX;
                resizeStartWidth = DOM.fbAlbumsMasterPane.offsetWidth;
                document.addEventListener('mousemove', handleResize);
                document.addEventListener('mouseup', stopResize);
                if (DOM.fbAlbumsResizeHandle) {
                    DOM.fbAlbumsResizeHandle.style.backgroundColor = '#2196F3';
                }
            }

            function handleResize(e) {
                if (resizeStartX === null || resizeStartWidth === null) return;
                
                const diff = e.clientX - resizeStartX;
                const newWidth = resizeStartWidth + diff;
                const minWidth = 200;
                const maxWidth = 600;
                
                if (newWidth >= minWidth && newWidth <= maxWidth) {
                    DOM.fbAlbumsMasterPane.style.width = newWidth + 'px';
                }
            }

            function stopResize() {
                resizeStartX = null;
                resizeStartWidth = null;
                document.removeEventListener('mousemove', handleResize);
                document.removeEventListener('mouseup', stopResize);
                if (DOM.fbAlbumsResizeHandle) {
                    DOM.fbAlbumsResizeHandle.style.backgroundColor = 'transparent';
                }
            }

            async function open() {
                Modals._openModal(DOM.fbAlbumsModal);
                selectedAlbumId = null;
                await loadAlbums();
                
                // Reset slave pane
                if (DOM.fbAlbumsAlbumTitle) {
                    DOM.fbAlbumsAlbumTitle.textContent = 'Select an album';
                }
                if (DOM.fbAlbumsAlbumDescription) {
                    DOM.fbAlbumsAlbumDescription.textContent = '';
                }
                if (DOM.fbAlbumsImagesContainer) {
                    DOM.fbAlbumsImagesContainer.innerHTML = '<div style="text-align: center; padding: 2rem; color: #666; grid-column: 1 / -1;">Select an album to view images</div>';
                }
            }

            async function openAndSelectAlbum(albumId) {
                // Open the Facebook Albums modal
                Modals._openModal(DOM.fbAlbumsModal);
                await loadAlbums();
                await selectAlbum(albumId);
                

            }


            function close() { 
                Modals._closeModal(DOM.fbAlbumsModal);
            }

            function init() {
                if (DOM.closeFBAlbumsModalBtn) {
                    DOM.closeFBAlbumsModalBtn.addEventListener('click', close);
                }
                if (DOM.fbAlbumsModal) {
                    DOM.fbAlbumsModal.addEventListener('click', (e) => {
                        if (e.target === DOM.fbAlbumsModal) close();
                    });
                }
                if (DOM.fbAlbumsSearch) {
                    DOM.fbAlbumsSearch.addEventListener('input', (e) => {
                        searchAlbums(e.target.value);
                    });
                }
                if (DOM.fbAlbumsResizeHandle) {
                    DOM.fbAlbumsResizeHandle.addEventListener('mousedown', startResize);
                }
            }

            async function openAndSelectAlbum(albumId) {
                // Open the Facebook Albums modal
                Modals._openModal(DOM.fbAlbumsModal);
                
                // Load albums and wait for them to load
                try {
                    await loadAlbums();
                    
                    // Find album by ID (handle both string and number comparisons)
                    const albumIdNum = typeof albumId === 'string' ? parseInt(albumId) : albumId;
                    const album = albums.find(a => {
                        const aId = typeof a.id === 'string' ? parseInt(a.id) : a.id;
                        return aId === albumIdNum || a.id === albumId || a.id === albumIdNum;
                    });
                    
                    if (album) {
                        // Select the album (this will also load its images)
                        // Use the album's actual ID to ensure type matching
                        await selectAlbum(album.id);
                    } else {
                        console.warn(`Album with ID ${albumId} not found`);
                        // Reset slave pane if album not found
                        if (DOM.fbAlbumsAlbumTitle) {
                            DOM.fbAlbumsAlbumTitle.textContent = 'Select an album';
                        }
                        if (DOM.fbAlbumsAlbumDescription) {
                            DOM.fbAlbumsAlbumDescription.textContent = '';
                        }
                        if (DOM.fbAlbumsImagesContainer) {
                            DOM.fbAlbumsImagesContainer.innerHTML = '<div style="text-align: center; padding: 2rem; color: #666; grid-column: 1 / -1;">Album not found</div>';
                        }
                    }
                } catch (error) {
                    console.error('Error loading albums:', error);
                }
            }

            return {
                open,
                close,
                init,
                startResize,
                openAndSelectAlbum
            };
        })(),
        


        Locations: (() => {

            let geoData = [];
            let fbData =[];
            let photoPlacesData = [];
            let mapViewInitialized = false;

            let selectedIdx = -1;
            let map = null;
            let mapView = null;
            let photoMarkersLayer = null;
            let currentPhotoIndex = 0;
            let layerControl = null;

            let biographyMarkers = [];
            let fbMarkers = []
            let otherMarkers = []
            let whatsappMarkers = []
            let emailMarkers = []
            let messageMarkers = []
            let photoMarkers = []
            let activePhotoMarkers = []

            let biographItems = [];
            let fbItems = []
            let otherItems = []
            let whatsappItems = []
            let emailItems = []
            let messageItems = []
            let photoItems = []

            function init() {
                if (DOM.geoMapFixedBtn) DOM.geoMapFixedBtn.addEventListener('click', _openGeoMapInNewTab);
                if (DOM.closeGeoMetadataModalBtn) DOM.closeGeoMetadataModalBtn.addEventListener('click', close);
                if (DOM.shufflePhotosBtn) DOM.shufflePhotosBtn.addEventListener('click', shufflePhotoMarkers);
                if (DOM.refreshLocationsBtn) DOM.refreshLocationsBtn.addEventListener('click', refresh);
            }


            function shufflePhotoMarkers() {
                if (!mapView || !photoMarkersLayer || !layerControl) return;
                
                // Remove existing photo markers layer from both map and layer control
                mapView.removeLayer(photoMarkersLayer);
                layerControl.removeLayer(photoMarkersLayer);
                
                // Create new photo markers with new random starting index
                
                //randomly select 200 markers from photoMarkers and add to activePhotoMarkers
                                 // Fisher-Yates shuffle function for uniform random distribution
                function shuffleArray(array) {
                                    const shuffled = [...array]; // Create a copy to avoid mutating the original
                                    for (let i = shuffled.length - 1; i > 0; i--) {
                                        const j = Math.floor(Math.random() * (i + 1));
                                        [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
                                    }
                                    return shuffled;
                }
                //activePhotoMarkers = [...photoMarkers].sort(() => Math.random() - 0.5).slice(0, 200);
                activePhotoMarkers = shuffleArray(photoMarkers).slice(0, 200);
                
                // Create new layer and add to map and layer control
                photoMarkersLayer = L.layerGroup(activePhotoMarkers).addTo(mapView);
                layerControl.addOverlay(photoMarkersLayer, 'GPS Photos Locations ('+photoMarkers.length+')');
                
                // Update the count display
                document.getElementById('geo-metadata-shown-count').textContent = 'Showing 200 of '+photoItems.length+' photos (Shuffled!)';

                mapView.invalidateSize();
            }

            function open() {
                Modals._openModal(DOM.geoMetadataModal);
                // DOM.geoList.innerHTML = '';
                if (geoData.length === 0 || photoPlacesData.length === 0) {
                    fetch('/getLocations').then(r => r.json()).then(data => {
                        geoData = data.locations || [];
                        mapViewInitialized = false;
                        fetch('/facebook/places').then(r => r.json()).then(data => {
                            fbData = data.places || [];
                            _initMapView();
                        });
                    });
                } else {
                    if (geoData.length > 0) _selectLocation(selectedIdx >= 0 ? selectedIdx : 0);
                }


            }
            
            function refresh() {
                // Fetch fresh data from server
                fetch('/getLocations').then(r => r.json()).then(data => {
                    geoData = data.locations || [];
                    
                    // Reset map state
                    mapViewInitialized = false;
                    
                    // Clear existing map if it exists
                    if (mapView) {
                        mapView.remove();
                        mapView = null;
                    }
                    
                    // Clear marker arrays
                    biographyMarkers = [];
                    fbMarkers = [];
                    otherMarkers = [];
                    whatsappMarkers = [];
                    emailMarkers = [];
                    messageMarkers = [];
                    photoMarkers = [];
                    activePhotoMarkers = [];
                    
                    // Clear item arrays
                    biographItems = [];
                    fbItems = [];
                    otherItems = [];
                    whatsappItems = [];
                    emailItems = [];
                    messageItems = [];
                    photoItems = [];
                    
                    // Reset other state
                    photoMarkersLayer = null;
                    layerControl = null;
                    selectedIdx = -1;
                    
                    // Reinitialize map with fresh data
                    _initMapView();
                }).catch(error => {
                    console.error('Error refreshing location data:', error);
                });
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
                }else {
                    mapView.setView([0, 0], 1);
                }
                layerControl = L.control.layers().addTo(mapView);
                mapView.invalidateSize();

                var darkBlueMarker = L.icon({
                    iconUrl: '/static/images/marker-dark-blue.png',
                    iconSize: [25, 35],
                    iconAnchor: [12, 32],
                    popupAnchor: [0, -32]
                });


                
                // Create photo markers using the extracted function
                //const { photoMarkers, photoShown, currentPhotoIndex } = _createPhotoMarkers();

                geoData.forEach(item => {
                    if (!item.latitude || !item.longitude) {
                        return;
                    }

                    switch (item.source) {
                        case 'Filesystem':
                            photoItems.push(item);
                            break;
                        case 'biography':
                            biographyItems.push(item);
                            break;
                        case 'facebook_album':
                            console.log("FB Album Item")
                            fbItems.push(item);
                            break;
                        case 'WhatsApp':
                            whatsappItems.push(item);
                            break;
                        case 'email_attachment':
                            emailItems.push(item);
                            break;
                        case 'message':
                        case 'imessage':
                        case 'message_attachment':
                            messageItems.push(item);
                            break;
                        default:
                            otherItems.push(item);
                            break;
                    }
                });

                // Helper function to handle marker click - fetch full image data and open detail modal
                async function handleMarkerClick(item, allowRedirects = false) {
                    try {
                        // Fetch full image metadata from API
                        const response = await fetch(`/images/${item.id}/metadata`);
                        if (!response.ok) {
                            throw new Error(`Failed to fetch image metadata: ${response.status}`);
                        }
                        const fullImageData = await response.json();

                        
                        // Open detail modal with full image data (don't allow redirects from Locations)
                        Modals.ImageDetailModal.open(fullImageData, {
                            allowRedirects: allowRedirects
                        });
                    } catch (error) {
                        console.error('Error fetching image metadata:', error);
                        // Fallback to basic display if fetch fails
                        const imageUrl = `/images/${item.id}?type=metadata`;
                        const filename = item.title || item.source_reference || `Image ${item.id}`;
                        Modals.SingleImageDisplay.showSingleImageModal(
                            filename,
                            imageUrl,
                            item.created_at,
                            item.latitude,
                            item.longitude
                        );
                    }
                }

                photoItems.forEach(item => {
                    const marker = L.marker([item.latitude, item.longitude], {icon: darkBlueMarker});
                    
                    // Add click handler to display image in modal
                    marker.on('click', function() {
                        handleMarkerClick(item);
                    });
                    
                    photoMarkers.push(marker);
                });

                messageItems.forEach(item => {
                    const marker = L.marker([item.latitude, item.longitude], {icon: darkBlueMarker});
                    marker.on('click', function() {
                        handleMarkerClick(item);
                    });
                    messageMarkers.push(marker);
                });

                emailItems.forEach(item => {
                    const marker = L.marker([item.latitude, item.longitude], {icon: darkBlueMarker});
                    marker.on('click', function() {
                        handleMarkerClick(item, true);
                    });
                    emailMarkers.push(marker);
                });
                biographItems.forEach(item => {
                    const marker = L.marker([item.latitude, item.longitude], {icon: darkBlueMarker});
                    marker.on('click', function() {
                        handleMarkerClick(item);
                    });
                    marker.bindPopup(item.destination);
                    biographyMarkers.push(marker);
                });
                fbData.forEach(item => {
                    if (!item.latitude || !item.longitude) return; // Skip items without coordinates
                    const marker = L.marker([item.latitude, item.longitude], {icon: darkBlueMarker});
                    // marker.on('click', function() {
                    //     handleMarkerClick(item);
                    // });
                    marker.bindPopup(item.name || 'Facebook Place');
                    fbMarkers.push(marker);
                });
                otherItems.forEach(item => {
                    const marker = L.marker([item.latitude, item.longitude], {icon: darkBlueMarker});
                    marker.on('click', function() {
                        handleMarkerClick(item);
                    });
                    marker.bindPopup(item.destination);
                    otherMarkers.push(marker);
                });
                whatsappItems.forEach(item => {
                    const marker = L.marker([item.latitude, item.longitude], {icon: darkBlueMarker});
                    marker.on('click', function() {
                        handleMarkerClick(item);
                    });
                    marker.bindPopup(item.destination);
                    whatsappMarkers.push(marker);
                });

                 
                 // Fisher-Yates shuffle function for uniform random distribution
                 function shuffleArray(array) {
                     const shuffled = [...array]; // Create a copy to avoid mutating the original
                     for (let i = shuffled.length - 1; i > 0; i--) {
                         const j = Math.floor(Math.random() * (i + 1));
                         [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
                     }
                     return shuffled;
                 }
                 
                 // Initialize activePhotoMarkers with random 200 markers using uniform shuffle
                 activePhotoMarkers = shuffleArray(photoMarkers).slice(0, 200);
                 
                 photoMarkersLayer = L.layerGroup(activePhotoMarkers).addTo(mapView);
                 layerControl.addOverlay(photoMarkersLayer, 'GPS Photos Locations ('+photoMarkers.length+')');
                 var whatsappMarkersLayer = L.layerGroup(whatsappMarkers).addTo(mapView);
                 layerControl.addOverlay(whatsappMarkersLayer, 'WhatsApp Locations ('+whatsappMarkers.length+')');
                 var emailMarkersLayer = L.layerGroup(emailMarkers).addTo(mapView);
                 layerControl.addOverlay(emailMarkersLayer, 'Email Locations ('+emailMarkers.length+')');
                 var messageMarkersLayer = L.layerGroup(messageMarkers).addTo(mapView);
                 layerControl.addOverlay(messageMarkersLayer, 'Message Locations ('+messageMarkers.length+')');
                 var biographyMarkersLayer = L.layerGroup(biographyMarkers).addTo(mapView);
                 layerControl.addOverlay(biographyMarkersLayer, 'Biography Locations ('+biographyMarkers.length+')');
                var fbMarkersLayer = L.layerGroup(fbMarkers).addTo(mapView);
                layerControl.addOverlay(fbMarkersLayer, 'Facebook Locations ('+fbMarkers.length+')');
                 var otherMarkersLayer = L.layerGroup(otherMarkers).addTo(mapView);
                 layerControl.addOverlay(otherMarkersLayer, 'Other Locations ('+otherMarkers.length+')');


                mapView.invalidateSize();

                mapViewInitialized = true;

                //document.getElementById('geo-metadata-shown-count').textContent = 'Showing '+photoShown+' of '+currentPhotoIndex+' photos (Click Shuffle Photos to see different images)' ;
                // setTimeout(() => { mapView.invalidateSize(); }, 100);
            }

             return { init,open,openMapView,shufflePhotoMarkers,refresh};
        })(),

        EmailGallery: (() => {
            let emailData = [];
            let selectedEmailIndex = -1;
            let currentEmailId = null;
            let currentPage = 0;
            let itemsPerPage = 20;
            let isLoading = false;
            let hasMoreData = true;
            let searchTimeout = null;
            let viewMode = 'list'; // 'list' or 'grid'

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
                
                // Delete button handler
                if (DOM.emailDeleteBtn) {
                    DOM.emailDeleteBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        deleteEmail();
                    });
                }

                // Ask AI button and modal handlers
                const emailAskAIBtn = DOM.emailAskAIBtn;
                const emailAskAIModal = DOM.emailAskAIModal;
                const emailAskAICloseBtn = document.getElementById('email-ask-ai-close');
                const emailAskAICancelBtn = document.getElementById('email-ask-ai-cancel');
                const emailAskAISubmitBtn = document.getElementById('email-ask-ai-submit');
                const emailAskAIRadioButtons = document.querySelectorAll('input[name="email-ask-ai-option"]');
                const emailAskAIOtherTextarea = document.getElementById('email-ask-ai-other-text');
                const emailAskAIOtherInput = document.getElementById('email-ask-ai-other-input');

                if (emailAskAIBtn && emailAskAIModal) {
                    emailAskAIBtn.addEventListener('click', () => {
                        // Update email subject in modal
                        const emailSubjectEl = document.getElementById('email-ask-ai-email-subject');
                        const emailSubject = DOM.emailGalleryMetadataSubject?.textContent || 'Unknown Email';
                        if (emailSubjectEl) {
                            emailSubjectEl.textContent = emailSubject;
                        }
                        emailAskAIModal.style.display = 'flex';
                    });
                }

                if (emailAskAICloseBtn && emailAskAIModal) {
                    emailAskAICloseBtn.addEventListener('click', () => {
                        emailAskAIModal.style.display = 'none';
                    });
                }

                if (emailAskAICancelBtn && emailAskAIModal) {
                    emailAskAICancelBtn.addEventListener('click', () => {
                        emailAskAIModal.style.display = 'none';
                    });
                }

                if (emailAskAISubmitBtn) {
                    emailAskAISubmitBtn.addEventListener('click', () => {
                        // Functionality will be added later
                        const selectedOption = document.querySelector('input[name="email-ask-ai-option"]:checked')?.value;
                        const otherText = emailAskAIOtherInput?.value || '';


                        if (selectedOption === 'summarise') {
                            if (!emailData[selectedEmailIndex].sender) {
                                alert('No conversation selected');
                                return;
                            }

                            try {
                                // Open the conversation summary modal
                                // currentSession is already the chat session name (string)
                                Modals.ConversationSummary.openForEmailThread(emailData[selectedEmailIndex].sender);
                            } catch (error) {
                                console.error('Error opening conversation summary:', error);
                                alert('Failed to start conversation summarization. Please try again.');
                            }
                        }


                        // TODO: Implement AI functionality
                        emailAskAIModal.style.display = 'none';
                    });
                }

                // Toggle textarea visibility based on radio selection
                if (emailAskAIRadioButtons.length > 0 && emailAskAIOtherTextarea) {
                    emailAskAIRadioButtons.forEach(radio => {
                        radio.addEventListener('change', () => {
                            if (radio.value === 'other') {
                                emailAskAIOtherTextarea.style.display = 'block';
                            } else {
                                emailAskAIOtherTextarea.style.display = 'none';
                            }
                        });
                    });
                }

                // Close modal when clicking outside
                if (emailAskAIModal) {
                    emailAskAIModal.addEventListener('click', (e) => {
                        if (e.target === emailAskAIModal) {
                            emailAskAIModal.style.display = 'none';
                        }
                    });
                }
                
                // Attachment modal close handlers
                if (DOM.closeEmailAttachmentImageModal && DOM.emailAttachmentImageModal) {
                    DOM.closeEmailAttachmentImageModal.addEventListener('click', () => {
                        DOM.emailAttachmentImageModal.style.display = 'none';
                    });
                    DOM.emailAttachmentImageModal.addEventListener('click', (e) => {
                        if (e.target === DOM.emailAttachmentImageModal) {
                            DOM.emailAttachmentImageModal.style.display = 'none';
                        }
                    });
                }
                if (DOM.closeEmailAttachmentDocumentModal && DOM.emailAttachmentDocumentModal) {
                    DOM.closeEmailAttachmentDocumentModal.addEventListener('click', () => {
                        DOM.emailAttachmentDocumentModal.style.display = 'none';
                    });
                    DOM.emailAttachmentDocumentModal.addEventListener('click', (e) => {
                        if (e.target === DOM.emailAttachmentDocumentModal) {
                            DOM.emailAttachmentDocumentModal.style.display = 'none';
                        }
                    });
                }
                
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
                DOM.emailGalleryAttachmentsFilter.addEventListener('change', _handleAttachmentsFilter);
               // DOM.emailGalleryFolderFilter.addEventListener('change', _handleSearch);

                // Add scroll event listener for lazy loading
                DOM.emailGalleryList.addEventListener('scroll', _handleEmailListScroll);

                // Add keyboard navigation
                document.addEventListener('keydown', _handleKeydown);
                
                // View toggle handler
                if (DOM.emailGalleryViewToggle) {
                    DOM.emailGalleryViewToggle.addEventListener('click', _toggleViewMode);
                }
                
                // Initialize resizable panes
                _initResizablePanes();
                
                // Initialize view mode
                if (DOM.emailGalleryList) {
                    DOM.emailGalleryList.classList.add('email-gallery-list-view');
                }
            }
            
            function _toggleViewMode() {
                viewMode = viewMode === 'list' ? 'grid' : 'list';
                const listContainer = DOM.emailGalleryList;
                if (listContainer) {
                    listContainer.classList.toggle('email-gallery-grid-view', viewMode === 'grid');
                    listContainer.classList.toggle('email-gallery-list-view', viewMode === 'list');
                }
                if (DOM.emailGalleryViewToggle) {
                    const icon = DOM.emailGalleryViewToggle.querySelector('i');
                    if (icon) {
                        icon.className = viewMode === 'grid' ? 'fas fa-list' : 'fas fa-th';
                    }
                }
                // Re-render the list
                _renderEmailList();
            }
            
            function _initResizablePanes() {
                if (!DOM.emailGalleryDivider || !DOM.emailGalleryMasterPane || !DOM.emailGalleryDetailPane) {
                    return;
                }
                
                // Load saved divider position from localStorage
                const savedPosition = localStorage.getItem('emailGalleryDividerPosition');
                const defaultPosition = 35; // 35% for master pane
                const masterPaneWidth = savedPosition ? parseFloat(savedPosition) : defaultPosition;
                
                _setPaneWidths(masterPaneWidth);
                
                let isResizing = false;
                let startX = 0;
                let startMasterWidth = 0;
                
                DOM.emailGalleryDivider.addEventListener('mousedown', (e) => {
                    isResizing = true;
                    startX = e.clientX;
                    startMasterWidth = parseFloat(getComputedStyle(DOM.emailGalleryMasterPane).width);
                    document.body.style.cursor = 'col-resize';
                    document.body.style.userSelect = 'none';
                    e.preventDefault();
                });
                
                document.addEventListener('mousemove', (e) => {
                    if (!isResizing) return;
                    
                    const deltaX = e.clientX - startX;
                    const modalWidth = DOM.emailGalleryModal.offsetWidth;
                    const newMasterWidth = ((startMasterWidth + deltaX) / modalWidth) * 100;
                    
                    // Constrain between min and max
                    const minWidth = 20; // 20% minimum
                    const maxWidth = 70; // 70% maximum
                    const constrainedWidth = Math.max(minWidth, Math.min(maxWidth, newMasterWidth));
                    
                    _setPaneWidths(constrainedWidth);
                });
                
                document.addEventListener('mouseup', () => {
                    if (isResizing) {
                        isResizing = false;
                        document.body.style.cursor = '';
                        document.body.style.userSelect = '';
                        
                        // Save position to localStorage
                        const currentWidth = parseFloat(getComputedStyle(DOM.emailGalleryMasterPane).width);
                        const modalWidth = DOM.emailGalleryModal.offsetWidth;
                        const percentage = (currentWidth / modalWidth) * 100;
                        localStorage.setItem('emailGalleryDividerPosition', percentage.toString());
                    }
                });
            }
            
            function _setPaneWidths(masterPanePercentage) {
                if (!DOM.emailGalleryMasterPane || !DOM.emailGalleryDetailPane) {
                    return;
                }
                
                DOM.emailGalleryMasterPane.style.width = `${masterPanePercentage}%`;
                DOM.emailGalleryDetailPane.style.width = `${100 - masterPanePercentage}%`;
            }

            async function open() {
                DOM.emailGalleryModal.style.display = 'flex';
                _loadEmailData().catch(error => {
                    console.error('Error loading email data in open():', error);
                });
            }

            function close() {
                DOM.emailGalleryModal.style.display = 'none';
                selectedEmailIndex = -1;
                _clearEmailContent();
            }

            function _loadEmailData() {
                return new Promise((resolve, reject) => {
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
                            resolve(emailData);
                        })
                        .catch(error => {
                            console.error('Error in fetch:', error);
                            emailData = [];
                            reject(error);
                        });

                    } catch (error) {
                        console.error('Error loading email data:', error);
                        emailData = [];
                        reject(error);
                    }
                });
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
                DOM.emailGalleryAttachmentsFilter.checked = false;
                DOM.emailGalleryList.innerHTML = '';
                DOM.emailGalleryEmailContent.style.display = 'none';

                // Repopulate the year filter select with all the years from 1990 to 2040
                if (DOM.emailGalleryYearFilter) {
                    DOM.emailGalleryYearFilter.innerHTML = '';
                    
                    // Add "All Years" option
                    const allYearsOption = document.createElement('option');
                    allYearsOption.value = '0';
                    allYearsOption.textContent = 'All Years';
                    DOM.emailGalleryYearFilter.appendChild(allYearsOption);
                    
                    // Add years from 2040 down to 1990 (descending order)
                    for (let year = 2040; year >= 1990; year--) {
                        const option = document.createElement('option');
                        option.value = year.toString();
                        option.textContent = year.toString();
                        DOM.emailGalleryYearFilter.appendChild(option);
                    }
                }
                
                // Repopulate the month filter select with all months
                if (DOM.emailGalleryMonthFilter) {
                    DOM.emailGalleryMonthFilter.innerHTML = '';
                    
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
                    
                    months.forEach(month => {
                        const option = document.createElement('option');
                        option.value = month.value.toString();
                        option.textContent = month.text;
                        DOM.emailGalleryMonthFilter.appendChild(option);
                    });
                }
                
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

                // Create table structure for grid/compact view
                if (viewMode === 'grid') {
                    const table = document.createElement('table');
                    table.className = 'email-gallery-table';
                    const thead = document.createElement('thead');
                    thead.innerHTML = `
                        <tr>
                            <th class="email-table-col-subject">Subject</th>
                            <th class="email-table-col-sender">From</th>
                            <th class="email-table-col-date">Date</th>
                            <th class="email-table-col-attachments"></th>
                        </tr>
                    `;
                    table.appendChild(thead);
                    const tbody = document.createElement('tbody');
                    tbody.id = 'email-gallery-table-body';
                    table.appendChild(tbody);
                    DOM.emailGalleryList.appendChild(table);
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
                
                // Get the correct container for appending items
                let container;
                if (viewMode === 'grid') {
                    container = document.getElementById('email-gallery-table-body');
                    if (!container) {
                        // Table not created yet, create it
                        const table = document.createElement('table');
                        table.className = 'email-gallery-table';
                        const thead = document.createElement('thead');
                        thead.innerHTML = `
                            <tr>
                                <th class="email-table-col-subject">Subject</th>
                                <th class="email-table-col-sender">From</th>
                                <th class="email-table-col-date">Date</th>
                                <th class="email-table-col-attachments"></th>
                            </tr>
                        `;
                        table.appendChild(thead);
                        const tbody = document.createElement('tbody');
                        tbody.id = 'email-gallery-table-body';
                        table.appendChild(tbody);
                        DOM.emailGalleryList.appendChild(table);
                        container = tbody;
                    }
                } else {
                    container = DOM.emailGalleryList;
                }

                emailsToRender.forEach((email, localIndex) => {
                 
                    const actualIndex = startIndex + localIndex;

                    if (viewMode === 'grid') {
                        // Compact table view - single line
                        if (!container) return;
                        
                        const row = document.createElement('tr');
                        row.className = 'email-table-row';
                        row.dataset.index = actualIndex;
                        
                        // Add has-attachments class if email has attachments
                        if (email.attachments && email.attachments.length > 0) {
                            row.classList.add('has-attachments');
                        }

                        row.innerHTML = `
                            <td class="email-table-col-subject">
                                <div class="email-table-subject">${email.subject || 'No Subject'}</div>
                            </td>
                            <td class="email-table-col-sender">
                                <div class="email-table-sender">${email.sender || 'Unknown Sender'}</div>
                            </td>
                            <td class="email-table-col-date">
                                <div class="email-table-date">${email.date || 'No Date'}</div>
                            </td>
                            <td class="email-table-col-attachments">
                                ${email.attachments && email.attachments.length > 0 ? '<span class="email-attachment-indicator">📎</span>' : ''}
                            </td>
                        `;

                        row.addEventListener('click', () => _selectEmail(actualIndex));
                        container.appendChild(row);
                    } else {
                        // List view - cards
                        if (!container) return;
                        
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
                        container.appendChild(emailItem);
                    }
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
                document.querySelectorAll('.email-list-item, .email-table-row').forEach((item) => {
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

            async function _displayEmail(email) {
                // Show email content, hide instructions
                DOM.emailGalleryInstructions.style.display = 'none';
                DOM.emailGalleryEmailContent.style.display = 'flex';
                
                // Store current email ID for delete/ask AI operations
                currentEmailId = email.emailId || email.id || null;
                
                // Show buttons
                if (DOM.emailAskAIBtn) {
                    DOM.emailAskAIBtn.style.display = 'flex';
                }
                if (DOM.emailDeleteBtn) {
                    DOM.emailDeleteBtn.style.display = 'flex';
                }
                
                // Update metadata
                if (DOM.emailGalleryMetadataSubject) {
                    DOM.emailGalleryMetadataSubject.textContent = email.subject || 'No Subject';
                }
                if (DOM.emailGalleryMetadataFrom) {
                    DOM.emailGalleryMetadataFrom.textContent = email.sender || 'Unknown Sender';
                }
                if (DOM.emailGalleryMetadataDate) {
                    DOM.emailGalleryMetadataDate.textContent = email.date || 'No Date';
                }
                if (DOM.emailGalleryMetadataFolder) {
                    DOM.emailGalleryMetadataFolder.textContent = email.folder || 'Unknown Folder';
                }
                
                // Show loading state
                if (DOM.emailGalleryIframe) {
                    DOM.emailGalleryIframe.style.display = 'none';
                }
                if (DOM.emailGalleryAttachmentsGrid) {
                    DOM.emailGalleryAttachmentsGrid.innerHTML = '<div class="email-attachment-loading">Loading attachments...</div>';
                }
                
                // Load email HTML into iframe
                if (email.emailId && DOM.emailGalleryIframe) {
                    try {
                        const response = await fetch(`/emails/${email.emailId}/html`);
                        if (response.ok) {
                            const htmlContent = await response.text();
                            DOM.emailGalleryIframe.srcdoc = htmlContent;
                            DOM.emailGalleryIframe.style.display = 'block';
                        } else {
                            // Fallback to plain text
                            const textResponse = await fetch(`/emails/${email.emailId}/text`);
                            if (textResponse.ok) {
                                const textContent = await textResponse.text();
                                const wrappedHtml = `<!DOCTYPE html>
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
${textContent}
</body>
</html>`;
                                DOM.emailGalleryIframe.srcdoc = wrappedHtml;
                                DOM.emailGalleryIframe.style.display = 'block';
                            } else {
                                throw new Error('Failed to fetch email content');
                            }
                        }
                    } catch (error) {
                        console.error('Error fetching email content:', error);
                        if (DOM.emailGalleryIframe) {
                            DOM.emailGalleryIframe.srcdoc = `<html><body style="padding: 20px; color: #c33; text-align: center;">Error loading email: ${error.message}</body></html>`;
                            DOM.emailGalleryIframe.style.display = 'block';
                        }
                    }
                }
                
                // Fetch and display attachments
                if (email.emailId && email.attachments && email.attachments.length > 0) {
                    await _loadAttachments(email.emailId, email.attachments);
                } else {
                    if (DOM.emailGalleryAttachmentsGrid) {
                        DOM.emailGalleryAttachmentsGrid.innerHTML = '<div class="email-attachment-empty">No attachments</div>';
                    }
                }
            }

            async function _loadAttachments(emailId, attachmentUrls) {
                if (!DOM.emailGalleryAttachmentsGrid) {
                    return;
                }
                
                DOM.emailGalleryAttachmentsGrid.innerHTML = '';
                
                // Extract attachment IDs from URLs
                const attachmentIds = attachmentUrls.map(url => {
                    const match = url.match(/\/attachments\/(\d+)/);
                    return match ? parseInt(match[1]) : null;
                }).filter(id => id !== null);
                
                // Fetch attachment info for each
                const attachmentPromises = attachmentIds.map(id => 
                    fetch(`/attachments/${id}/info`)
                        .then(r => r.json())
                        .catch(err => {
                            console.error(`Error fetching attachment ${id} info:`, err);
                            return null;
                        })
                );
                
                const attachmentInfos = await Promise.all(attachmentPromises);
                
                // Render each attachment
                attachmentInfos.forEach((info, index) => {
                    if (!info) return;
                    
                    const attachmentElement = _createAttachmentElement(info, attachmentIds[index]);
                    DOM.emailGalleryAttachmentsGrid.appendChild(attachmentElement);
                });
            }
            
            function _createAttachmentElement(attachmentInfo, attachmentId) {
                const container = document.createElement('div');
                container.className = 'email-attachment-item';
                container.dataset.attachmentId = attachmentId;
                
                const isImage = attachmentInfo.content_type && attachmentInfo.content_type.startsWith('image/');
                
                if (isImage) {
                    // Image attachment - show thumbnail preview
                    const img = document.createElement('img');
                    img.className = 'email-attachment-thumbnail';
                    img.src = `/attachments/${attachmentId}?preview=true`;
                    img.alt = attachmentInfo.filename || 'Attachment';
                    img.loading = 'lazy';
                    container.appendChild(img);
                } else {
                    // Non-image attachment - show icon
                    const iconContainer = document.createElement('div');
                    iconContainer.className = 'email-attachment-icon-container';
                    const icon = _getAttachmentIcon(attachmentInfo.content_type);
                    iconContainer.innerHTML = `<i class="${icon.class}" style="font-size: 3em; color: ${icon.color};"></i>`;
                    container.appendChild(iconContainer);
                }
                
                // Add filename label
                const filenameLabel = document.createElement('div');
                filenameLabel.className = 'email-attachment-filename';
                filenameLabel.textContent = attachmentInfo.filename || `Attachment ${attachmentId}`;
                filenameLabel.title = attachmentInfo.filename || `Attachment ${attachmentId}`;
                container.appendChild(filenameLabel);
                
                // Add click handler
                container.addEventListener('click', () => {
                    _viewAttachment(attachmentId, attachmentInfo, isImage);
                });
                
                return container;
            }
            
            function _getAttachmentIcon(contentType) {
                if (!contentType) {
                    return { class: 'fas fa-file', color: '#666' };
                }
                
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
                
                if (contentType.includes('zip') || contentType.includes('archive')) {
                    return { class: 'fas fa-file-archive', color: '#ffc107' };
                }
                
                if (contentType.includes('text')) {
                    return { class: 'fas fa-file-alt', color: '#17a2b8' };
                }
                
                return { class: 'fas fa-file', color: '#666' };
            }
            
            function _viewAttachment(attachmentId, attachmentInfo, isImage) {
                if (isImage) {
                    // Show image in image modal
                    if (DOM.emailAttachmentImageDisplay && DOM.emailAttachmentImageModal) {
                        DOM.emailAttachmentImageDisplay.src = `/attachments/${attachmentId}`;
                        DOM.emailAttachmentImageDisplay.alt = attachmentInfo.filename || 'Attachment';
                        DOM.emailAttachmentImageModal.style.display = 'flex';
                    }
                } else {
                    // Show document in iframe modal
                    if (DOM.emailAttachmentDocumentIframe && DOM.emailAttachmentDocumentModal) {
                        DOM.emailAttachmentDocumentIframe.src = `/attachments/${attachmentId}`;
                        DOM.emailAttachmentDocumentModal.style.display = 'flex';
                    }
                }
            }

            function _showInstructions() {
                DOM.emailGalleryInstructions.style.display = 'flex';
                DOM.emailGalleryEmailContent.style.display = 'none';
                
                // Hide buttons
                if (DOM.emailAskAIBtn) {
                    DOM.emailAskAIBtn.style.display = 'none';
                }
                if (DOM.emailDeleteBtn) {
                    DOM.emailDeleteBtn.style.display = 'none';
                }
                
                // Clear current email ID
                currentEmailId = null;
            }

            function _clearEmailContent() {
                if (DOM.emailGalleryIframe) {
                    DOM.emailGalleryIframe.srcdoc = '';
                }
                if (DOM.emailGalleryAttachmentsGrid) {
                    DOM.emailGalleryAttachmentsGrid.innerHTML = '';
                }
                if (DOM.emailGalleryMetadataSubject) {
                    DOM.emailGalleryMetadataSubject.textContent = '';
                }
                if (DOM.emailGalleryMetadataFrom) {
                    DOM.emailGalleryMetadataFrom.textContent = '';
                }
                if (DOM.emailGalleryMetadataDate) {
                    DOM.emailGalleryMetadataDate.textContent = '';
                }
                if (DOM.emailGalleryMetadataFolder) {
                    DOM.emailGalleryMetadataFolder.textContent = '';
                }
                
                // Hide buttons
                if (DOM.emailAskAIBtn) {
                    DOM.emailAskAIBtn.style.display = 'none';
                }
                if (DOM.emailDeleteBtn) {
                    DOM.emailDeleteBtn.style.display = 'none';
                }
                
                // Clear current email ID
                currentEmailId = null;
            }

            async function deleteEmail() {
                if (!currentEmailId) return;

                // Get email subject for confirmation message
                const emailSubject = DOM.emailGalleryMetadataSubject?.textContent || 'this email';
                const emailIdToDelete = currentEmailId;
                
                // Show confirmation dialog
                const confirmed = confirm(`Are you sure you want to delete "${emailSubject}"?\n\nThis action cannot be undone.`);
                if (!confirmed) {
                    return;
                }

                try {
                    const response = await fetch(`/emails/${emailIdToDelete}`, {
                        method: 'DELETE'
                    });

                    if (!response.ok) {
                        const error = await response.json();
                        throw new Error(error.detail || 'Failed to delete email');
                    }

                    const result = await response.json();
                    
                    // Remove from emailData array before clearing view
                    const emailIndex = emailData.findIndex(e => (e.emailId || e.id) === emailIdToDelete);
                    if (emailIndex !== -1) {
                        emailData.splice(emailIndex, 1);
                    }

                    // Clear the email view
                    currentEmailId = null;
                    selectedEmailIndex = -1;
                    _showInstructions();
                    _clearEmailContent();

                    // Remove active state from all items
                    const items = document.querySelectorAll('.email-list-item, .email-table-row');
                    items.forEach(item => item.classList.remove('selected'));

                    // Reload email list
                    await _handleSearch();
                    
                    alert(`Successfully deleted email: ${emailSubject}`);
                } catch (error) {
                    console.error('Error deleting email:', error);
                    alert(`Error deleting email: ${error.message}`);
                }
            }

            function _updateEmailDetails() {
                // Email details are now displayed in the iframe and attachment grid
                // This function is kept for potential future use
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
                const selectedItem = document.querySelector('.email-list-item.selected, .email-table-row.selected');
                if (selectedItem) {
                    selectedItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            }

            async function openAndSelectEmail(emailId) {
                // Open the Email Gallery modal
                DOM.emailGalleryModal.style.display = 'flex';
                
                try {
                    // First, fetch the email metadata to get its properties
                    const metadataResponse = await fetch(`/emails/${emailId}/metadata`);
                    if (!metadataResponse.ok) {
                        throw new Error(`Failed to fetch email metadata: ${metadataResponse.status}`);
                    }
                    
                    const emailMetadata = await metadataResponse.json();
                    
                    // Extract date information
                    let year = 0;
                    let month = 0;
                    if (emailMetadata.date) {
                        const emailDate = new Date(emailMetadata.date);
                        if (!isNaN(emailDate.getTime())) {
                            year = emailDate.getFullYear();
                            month = emailDate.getMonth() + 1; // JavaScript months are 0-indexed
                        }
                    }
                    
                    // Set filters to match the email's properties
                    DOM.emailGallerySearch.value = '';
                    DOM.emailGallerySender.value = emailMetadata.from_address || '';
                    DOM.emailGalleryRecipient.value = '';
                    DOM.emailGalleryToFrom.value = emailMetadata.from_address || '';
                    DOM.emailGalleryYearFilter.value = year > 0 ? year.toString() : '0';
                    DOM.emailGalleryMonthFilter.value = month > 0 ? month.toString() : '0';
                    DOM.emailGalleryAttachmentsFilter.checked = false;
                    
                    // Build query parameters based on the email's properties
                    const params = new URLSearchParams();
                    if (emailMetadata.from_address) {
                        params.append('from_address', emailMetadata.from_address);
                    }
                    if (year > 0) {
                        params.append('year', year.toString());
                    }
                    if (month > 0) {
                        params.append('month', month.toString());
                    }
                    
                    // Load emails with filters matching the email
                    const searchResponse = await fetch('/emails/search?' + params.toString());
                    if (!searchResponse.ok) {
                        throw new Error(`Failed to search emails: ${searchResponse.status}`);
                    }
                    
                    const data = await searchResponse.json();
                    
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
                    
                    // Find email index by ID
                    const emailIndex = emailData.findIndex(email => 
                        (email.emailId === emailId) || (email.id === emailId)
                    );
                    
                    if (emailIndex !== -1) {
                        _selectEmail(emailIndex);
                        _scrollToSelectedEmail();
                    } else {
                        console.warn(`Email with ID ${emailId} not found in filtered results`);
                        // Show instructions since email wasn't found
                        _showInstructions();
                    }
                } catch (error) {
                    console.error('Error loading email:', error);
                    alert('Failed to load email. Please try again.');
                    _showInstructions();
                }
            }

            return { init, open, close, openContact, openAndSelectEmail };
        })(),

        EmailEditor: (() => {
            let emailData = [];
            let currentPage = 1;
            let pageSize = 50;
            let selectedRowIndex = -1;
            let selectedEmailIds = new Set();

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

            function _truncateText(text, maxLength) {
                if (!text) return '';
                if (text.length <= maxLength) return text;
                return text.substring(0, maxLength - 3) + '...';
            }

            function _setupFilters() {
                // Setup year filter
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
                ];
                
                if (DOM.emailEditorYearFilter) {
                    DOM.emailEditorYearFilter.innerHTML = '';
                    years.forEach(year => {
                        const option = document.createElement('option');
                        option.value = year.value;
                        option.textContent = year.text;
                        DOM.emailEditorYearFilter.appendChild(option);
                    });
                }

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
                
                if (DOM.emailEditorMonthFilter) {
                    DOM.emailEditorMonthFilter.innerHTML = '';
                    months.forEach(month => {
                        const option = document.createElement('option');
                        option.value = month.value;
                        option.textContent = month.text;
                        DOM.emailEditorMonthFilter.appendChild(option);
                    });
                }
            }

            function init() {
                DOM.closeEmailEditorModalBtn.addEventListener('click', close);
                DOM.emailEditorSearchBtn.addEventListener('click', _handleSearch);
                DOM.emailEditorClearBtn.addEventListener('click', _handleClear);
                if (DOM.emailEditorBulkDeleteBtn) {
                    DOM.emailEditorBulkDeleteBtn.addEventListener('click', _handleBulkDelete);
                }
                _setupFilters();
            }

            function _handleSearch() {
                currentPage = 1;
                _loadEmails();
            }

            function _handleClear() {
                DOM.emailEditorSearch.value = '';
                DOM.emailEditorSender.value = '';
                DOM.emailEditorRecipient.value = '';
                DOM.emailEditorToFrom.value = '';
                DOM.emailEditorYearFilter.value = '0';
                DOM.emailEditorMonthFilter.value = '0';
                DOM.emailEditorAttachmentsFilter.checked = false;
                currentPage = 1;
                _loadEmails();
            }

            function _loadEmails() {
                const params = new URLSearchParams();
                const searchTerm = DOM.emailEditorSearch.value.trim();
                const senderFilter = DOM.emailEditorSender.value.trim();
                const recipientFilter = DOM.emailEditorRecipient.value.trim();
                const toFromFilter = DOM.emailEditorToFrom.value.trim();
                const yearFilter = DOM.emailEditorYearFilter.value;
                const monthFilter = DOM.emailEditorMonthFilter.value;
                const attachmentsFilter = DOM.emailEditorAttachmentsFilter.checked;

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

                fetch('/emails/search?' + params.toString())
                    .then(r => r.json())
                    .then(data => {
                        emailData = data.map(email => ({
                            id: email.id,
                            subject: email.subject || 'No Subject',
                            sender: email.from_address || 'Unknown Sender',
                            recipient: email.to_addresses || 'Unknown Recipient',
                            date: email.date ? formatDateAustralian(email.date) : 'No Date',
                            emailId: email.id,
                            is_personal: email.is_personal || false,
                            is_business: email.is_business || false,
                            is_important: email.is_important || false,
                            use_by_ai: email.use_by_ai !== undefined ? email.use_by_ai : true
                        }));
                        _renderTable();
                        _renderPagination();
                    })
                    .catch(error => {
                        console.error('Error loading emails:', error);
                        emailData = [];
                        _renderTable();
                        _renderPagination();
                    });
            }

            function _renderTable() {
                if (!DOM.emailEditorTableBody) return;

                const startIndex = (currentPage - 1) * pageSize;
                const endIndex = startIndex + pageSize;
                const emailsToShow = emailData.slice(startIndex, endIndex);

                DOM.emailEditorTableBody.innerHTML = '';

                if (emailsToShow.length === 0) {
                    const row = document.createElement('tr');
                    const cell = document.createElement('td');
                    cell.colSpan = 4;
                    cell.textContent = 'No emails found';
                    cell.style.textAlign = 'center';
                    cell.style.padding = '2em';
                    cell.style.color = '#666';
                    row.appendChild(cell);
                    DOM.emailEditorTableBody.appendChild(row);
                    return;
                }

                emailsToShow.forEach((email, index) => {
                    const row = document.createElement('tr');
                    row.className = 'email-editor-table-row';
                    if (selectedRowIndex === startIndex + index) {
                        row.classList.add('selected');
                    }
                    row.dataset.index = startIndex + index;
                    row.dataset.emailId = email.id;

                    // Subject column
                    const subjectCell = document.createElement('td');
                    subjectCell.className = 'email-editor-col-subject';
                    subjectCell.textContent = _truncateText(email.subject, 60);
                    subjectCell.title = email.subject;
                    subjectCell.addEventListener('click', (e) => {
                        e.stopPropagation();
                        _selectRow(startIndex + index);
                    });
                    row.appendChild(subjectCell);

                    // From column
                    const fromCell = document.createElement('td');
                    fromCell.className = 'email-editor-col-from';
                    fromCell.textContent = _truncateText(email.sender, 40);
                    fromCell.title = email.sender;
                    fromCell.addEventListener('click', (e) => {
                        e.stopPropagation();
                        _selectRow(startIndex + index);
                    });
                    row.appendChild(fromCell);

                    // To column
                    const toCell = document.createElement('td');
                    toCell.className = 'email-editor-col-to';
                    toCell.textContent = _truncateText(email.recipient, 40);
                    toCell.title = email.recipient;
                    toCell.addEventListener('click', (e) => {
                        e.stopPropagation();
                        _selectRow(startIndex + index);
                    });
                    row.appendChild(toCell);

                    // Date column
                    const dateCell = document.createElement('td');
                    dateCell.className = 'email-editor-col-date';
                    dateCell.textContent = email.date;
                    dateCell.addEventListener('click', (e) => {
                        e.stopPropagation();
                        _selectRow(startIndex + index);
                    });
                    row.appendChild(dateCell);

                    // Personal column (editable)
                    const personalCell = document.createElement('td');
                    personalCell.className = 'email-editor-col-personal';
                    personalCell.innerHTML = email.is_personal ? '✓' : '';
                    personalCell.style.cursor = 'pointer';
                    personalCell.style.textAlign = 'center';
                    personalCell.style.fontWeight = 'bold';
                    personalCell.style.color = email.is_personal ? '#28a745' : '#ccc';
                    personalCell.addEventListener('click', (e) => {
                        e.stopPropagation();
                        _toggleField(email.id, 'is_personal', !email.is_personal);
                    });
                    row.appendChild(personalCell);

                    // Business column (editable)
                    const businessCell = document.createElement('td');
                    businessCell.className = 'email-editor-col-business';
                    businessCell.innerHTML = email.is_business ? '✓' : '';
                    businessCell.style.cursor = 'pointer';
                    businessCell.style.textAlign = 'center';
                    businessCell.style.fontWeight = 'bold';
                    businessCell.style.color = email.is_business ? '#28a745' : '#ccc';
                    businessCell.addEventListener('click', (e) => {
                        e.stopPropagation();
                        _toggleField(email.id, 'is_business', !email.is_business);
                    });
                    row.appendChild(businessCell);

                    // Important column (editable)
                    const importantCell = document.createElement('td');
                    importantCell.className = 'email-editor-col-important';
                    importantCell.innerHTML = email.is_important ? '✓' : '';
                    importantCell.style.cursor = 'pointer';
                    importantCell.style.textAlign = 'center';
                    importantCell.style.fontWeight = 'bold';
                    importantCell.style.color = email.is_important ? '#ffc107' : '#ccc';
                    importantCell.addEventListener('click', (e) => {
                        e.stopPropagation();
                        _toggleField(email.id, 'is_important', !email.is_important);
                    });
                    row.appendChild(importantCell);

                    // Use by AI column (editable)
                    const useByAiCell = document.createElement('td');
                    useByAiCell.className = 'email-editor-col-use-by-ai';
                    if (email.use_by_ai === true) {
                        useByAiCell.innerHTML = '✓';
                        useByAiCell.style.color = '#17a2b8';
                    } else {
                        useByAiCell.innerHTML = '✗';
                        useByAiCell.style.color = '#dc3545';
                    }
                    useByAiCell.style.cursor = 'pointer';
                    useByAiCell.style.textAlign = 'center';
                    useByAiCell.style.fontWeight = 'bold';
                    useByAiCell.addEventListener('click', (e) => {
                        e.stopPropagation();
                        // Toggle between true and false
                        _toggleField(email.id, 'use_by_ai', !email.use_by_ai);
                    });
                    row.appendChild(useByAiCell);

                    // Delete column (checkbox)
                    const deleteCell = document.createElement('td');
                    deleteCell.className = 'email-editor-col-delete';
                    deleteCell.style.textAlign = 'center';
                    const checkbox = document.createElement('input');
                    checkbox.type = 'checkbox';
                    checkbox.className = 'email-delete-checkbox';
                    checkbox.dataset.emailId = email.id;
                    checkbox.checked = selectedEmailIds.has(email.id);
                    checkbox.addEventListener('click', (e) => {
                        e.stopPropagation();
                        if (checkbox.checked) {
                            selectedEmailIds.add(email.id);
                        } else {
                            selectedEmailIds.delete(email.id);
                        }
                        _updateBulkDeleteButton();
                    });
                    deleteCell.appendChild(checkbox);
                    row.appendChild(deleteCell);

                    DOM.emailEditorTableBody.appendChild(row);
                });
            }

            function _selectRow(index) {
                selectedRowIndex = index;
                _renderTable();
            }

            function _toggleField(emailId, fieldName, newValue) {
                // Update local data immediately for responsive UI
                const email = emailData.find(e => e.id === emailId);
                if (email) {
                    email[fieldName] = newValue;
                }

                // Update on server
                fetch(`/emails/${emailId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ [fieldName]: newValue })
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Failed to update email');
                    }
                    return response.json();
                })
                .then(updatedEmail => {
                    // Update local data with server response
                    const emailIndex = emailData.findIndex(e => e.id === emailId);
                    if (emailIndex !== -1) {
                        emailData[emailIndex] = {
                            ...emailData[emailIndex],
                            is_personal: updatedEmail.is_personal,
                            is_business: updatedEmail.is_business,
                            is_important: updatedEmail.is_important,
                            use_by_ai: updatedEmail.use_by_ai
                        };
                    }
                    _renderTable();
                })
                .catch(error => {
                    console.error('Error updating email:', error);
                    // Revert local change on error
                    if (email) {
                        email[fieldName] = !newValue;
                    }
                    _renderTable();
                    alert('Failed to update email. Please try again.');
                });
            }

            function _updateBulkDeleteButton() {
                if (DOM.emailEditorBulkDeleteBtn) {
                    if (selectedEmailIds.size > 0) {
                        DOM.emailEditorBulkDeleteBtn.style.display = 'inline-block';
                        DOM.emailEditorBulkDeleteBtn.textContent = `Delete Selected (${selectedEmailIds.size})`;
                    } else {
                        DOM.emailEditorBulkDeleteBtn.style.display = 'none';
                    }
                }
            }

            function _handleBulkDelete() {
                if (selectedEmailIds.size === 0) {
                    return;
                }

                const emailIdsArray = Array.from(selectedEmailIds);
                const count = emailIdsArray.length;
                
                // Use the existing confirmation modal
                if (window.Modals && window.Modals.Confirmation) {
                    window.Modals.Confirmation.show(
                        'Delete Emails',
                        `Are you sure you want to delete ${count} email(s)? This action cannot be undone.`,
                        () => {
                            _bulkDeleteEmails(emailIdsArray);
                        }
                    );
                } else {
                    // Fallback to browser confirm
                    if (confirm(`Are you sure you want to delete ${count} email(s)? This action cannot be undone.`)) {
                        _bulkDeleteEmails(emailIdsArray);
                    }
                }
            }

            function _bulkDeleteEmails(emailIds) {
                fetch('/emails/bulk-delete', {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ email_ids: emailIds })
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Failed to delete emails');
                    }
                    return response.json();
                })
                .then(result => {
                    // Remove deleted emails from local data
                    emailIds.forEach(id => {
                        emailData = emailData.filter(e => e.id !== id);
                        selectedEmailIds.delete(id);
                    });
                    
                    // Reset to first page if current page is empty
                    const totalPages = Math.ceil(emailData.length / pageSize);
                    if (currentPage > totalPages && totalPages > 0) {
                        currentPage = totalPages;
                    } else if (totalPages === 0) {
                        currentPage = 1;
                    }
                    
                    _updateBulkDeleteButton();
                    _renderTable();
                    _renderPagination();
                    
                    if (result.errors && result.errors.length > 0) {
                        alert(`Deleted ${result.deleted_count} email(s). Some errors occurred:\n${result.errors.join('\n')}`);
                    } else {
                        alert(`Successfully deleted ${result.deleted_count} email(s).`);
                    }
                })
                .catch(error => {
                    console.error('Error bulk deleting emails:', error);
                    alert('Failed to delete emails. Please try again.');
                });
            }

            function _confirmDelete(emailId, emailSubject) {
                // Use the existing confirmation modal
                if (window.Modals && window.Modals.Confirmation) {
                    window.Modals.Confirmation.show(
                        'Delete Email',
                        `Are you sure you want to delete "${emailSubject}"? This action cannot be undone.`,
                        () => {
                            _deleteEmail(emailId);
                        }
                    );
                } else {
                    // Fallback to browser confirm
                    if (confirm(`Are you sure you want to delete "${emailSubject}"? This action cannot be undone.`)) {
                        _deleteEmail(emailId);
                    }
                }
            }

            function _deleteEmail(emailId) {
                fetch(`/emails/${emailId}`, {
                    method: 'DELETE'
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Failed to delete email');
                    }
                    return response.json();
                })
                .then(() => {
                    // Remove from local data
                    emailData = emailData.filter(e => e.id !== emailId);
                    selectedEmailIds.delete(emailId);
                    // Reset to first page if current page is empty
                    const totalPages = Math.ceil(emailData.length / pageSize);
                    if (currentPage > totalPages && totalPages > 0) {
                        currentPage = totalPages;
                    } else if (totalPages === 0) {
                        currentPage = 1;
                    }
                    _updateBulkDeleteButton();
                    _renderTable();
                    _renderPagination();
                })
                .catch(error => {
                    console.error('Error deleting email:', error);
                    alert('Failed to delete email. Please try again.');
                });
            }

            function _renderPagination() {
                if (!DOM.emailEditorPagination) return;

                const totalPages = Math.ceil(emailData.length / pageSize);
                
                if (totalPages <= 1) {
                    DOM.emailEditorPagination.innerHTML = '';
                    return;
                }

                let paginationHTML = '';

                // Previous button
                paginationHTML += `<button ${currentPage === 1 ? 'disabled' : ''} class="email-editor-prev-btn">Previous</button>`;

                // Page info
                paginationHTML += `<span class="email-editor-page-info">Page ${currentPage} of ${totalPages}</span>`;

                // Next button
                paginationHTML += `<button ${currentPage === totalPages ? 'disabled' : ''} class="email-editor-next-btn">Next</button>`;

                DOM.emailEditorPagination.innerHTML = paginationHTML;

                // Add event listeners
                const prevBtn = DOM.emailEditorPagination.querySelector('.email-editor-prev-btn');
                const nextBtn = DOM.emailEditorPagination.querySelector('.email-editor-next-btn');

                if (prevBtn) {
                    prevBtn.addEventListener('click', () => {
                        if (currentPage > 1) {
                            currentPage--;
                            _renderTable();
                            _renderPagination();
                        }
                    });
                }

                if (nextBtn) {
                    nextBtn.addEventListener('click', () => {
                        if (currentPage < totalPages) {
                            currentPage++;
                            _renderTable();
                            _renderPagination();
                        }
                    });
                }
            }

            function open() {
                DOM.emailEditorModal.style.display = 'flex';
                currentPage = 1;
                selectedRowIndex = -1;
                selectedEmailIds.clear();
                _updateBulkDeleteButton();
                //_loadEmails();
            }

            function close() {
                DOM.emailEditorModal.style.display = 'none';
                selectedRowIndex = -1;
            }

            return { init, open, close };
        })(),

        NewImageGallery: (() => {
            let imageData = [];
            let selectedImageIndex = -1;
            let currentPage = 0;
            let itemsPerPage = 20;
            let isLoading = false;
            let hasMoreData = true;
            let searchTimeout = null;
            let selectMode = false;
            let selectedImageIds = new Set(); // Track selected image IDs

            function formatDate(year, month) {
                if (!year && !month) return 'No Date';
                const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
                    'July', 'August', 'September', 'October', 'November', 'December'];
                if (year && month) {
                    return `${monthNames[month - 1]} ${year}`;
                } else if (year) {
                    return year.toString();
                } else if (month) {
                    return monthNames[month - 1];
                }
                return 'No Date';
            }

            function init() {
                DOM.closeNewImageGalleryModalBtn.addEventListener('click', close);
                DOM.newImageGallerySearchBtn.addEventListener('click', _handleSearch);
                DOM.newImageGalleryClearBtn.addEventListener('click', _handleClear);
                
                // Add event listeners for filter changes with debouncing
                const filterInputs = [
                    DOM.newImageGalleryTitle,
                    DOM.newImageGalleryDescription,
                    DOM.newImageGalleryTags,
                    DOM.newImageGalleryAuthor,
                    DOM.newImageGallerySource,
                    DOM.newImageGalleryYearFilter,
                    DOM.newImageGalleryMonthFilter,
                    DOM.newImageGalleryRating,
                    DOM.newImageGalleryRatingMin,
                    DOM.newImageGalleryRatingMax,
                    DOM.newImageGalleryHasGps,
                    DOM.newImageGalleryProcessed
                ];

                filterInputs.forEach(input => {
                    if (input) {
                        if (input.type === 'checkbox') {
                            input.addEventListener('change', () => {
                                if (searchTimeout) clearTimeout(searchTimeout);
                                searchTimeout = setTimeout(() => {
                                    _handleSearch();
                                }, 300);
                            });
                        } else {
                            input.addEventListener('input', () => {
                                if (searchTimeout) clearTimeout(searchTimeout);
                                searchTimeout = setTimeout(() => {
                                    _handleSearch();
                                }, 300);
                            });
                        }
                    }
                });
                
                // Add scroll event listener for lazy loading
                DOM.newImageGalleryThumbnailGrid.addEventListener('scroll', _handleThumbnailScroll);
                
                // Select mode toggle
                if (DOM.newImageGallerySelectMode) {
                    DOM.newImageGallerySelectMode.addEventListener('change', (e) => {
                        selectMode = e.target.checked;
                        _updateSelectModeUI();
                        if (!selectMode) {
                            // Clear selection when exiting select mode
                            selectedImageIds.clear();
                            _updateSelectionUI();
                        }
                    });
                }
                
                // Bulk tag application
                if (DOM.newImageGalleryApplyTagsBtn) {
                    DOM.newImageGalleryApplyTagsBtn.addEventListener('click', async () => {
                        await _applyTagsToSelected();
                    });
                }
                
                // Bulk delete selected images
                if (DOM.newImageGalleryDeleteSelectedBtn) {
                    DOM.newImageGalleryDeleteSelectedBtn.addEventListener('click', async () => {
                        await _deleteSelectedImages();
                    });
                }
                
                // Clear selection
                if (DOM.newImageGalleryClearSelectionBtn) {
                    DOM.newImageGalleryClearSelectionBtn.addEventListener('click', () => {
                        selectedImageIds.clear();
                        _updateSelectionUI();
                    });
                }
                
                // Enable/disable apply button based on tags input
                if (DOM.newImageGalleryBulkTags) {
                    DOM.newImageGalleryBulkTags.addEventListener('input', () => {
                        _updateSelectionUI();
                    });
                }
                
                // Initialize resizable panes
                _initResizablePanes();
                
                // Note: Detail modal handlers are now managed by Modals.ImageDetailModal.init()
            }
            
            function _initResizablePanes() {
                if (!DOM.newImageGalleryDivider || !DOM.newImageGalleryMasterPane || !DOM.newImageGalleryDetailPane) {
                    return;
                }
                
                // Load saved divider position from localStorage
                const savedPosition = localStorage.getItem('newImageGalleryDividerPosition');
                const defaultPosition = 35; // 35% for master pane
                const masterPaneWidth = savedPosition ? parseFloat(savedPosition) : defaultPosition;
                
                _setPaneWidths(masterPaneWidth);
                
                let isResizing = false;
                let startX = 0;
                let startMasterWidth = 0;
                
                DOM.newImageGalleryDivider.addEventListener('mousedown', (e) => {
                    isResizing = true;
                    startX = e.clientX;
                    startMasterWidth = parseFloat(getComputedStyle(DOM.newImageGalleryMasterPane).width);
                    document.body.style.cursor = 'col-resize';
                    document.body.style.userSelect = 'none';
                    e.preventDefault();
                });
                
                document.addEventListener('mousemove', (e) => {
                    if (!isResizing) return;
                    
                    const deltaX = e.clientX - startX;
                    const modalWidth = DOM.newImageGalleryModal.offsetWidth;
                    const newMasterWidth = ((startMasterWidth + deltaX) / modalWidth) * 100;
                    
                    // Constrain between min and max
                    const minWidth = 20; // 20% minimum
                    const maxWidth = 70; // 70% maximum
                    const constrainedWidth = Math.max(minWidth, Math.min(maxWidth, newMasterWidth));
                    
                    _setPaneWidths(constrainedWidth);
                });
                
                document.addEventListener('mouseup', () => {
                    if (isResizing) {
                        isResizing = false;
                        document.body.style.cursor = '';
                        document.body.style.userSelect = '';
                        
                        // Save position to localStorage
                        const currentWidth = parseFloat(getComputedStyle(DOM.newImageGalleryMasterPane).width);
                        const modalWidth = DOM.newImageGalleryModal.offsetWidth;
                        const percentage = (currentWidth / modalWidth) * 100;
                        localStorage.setItem('newImageGalleryDividerPosition', percentage.toString());
                    }
                });
            }
            
            function _setPaneWidths(masterPanePercentage) {
                if (!DOM.newImageGalleryMasterPane || !DOM.newImageGalleryDetailPane) {
                    return;
                }
                
                DOM.newImageGalleryMasterPane.style.width = `${masterPanePercentage}%`;
                DOM.newImageGalleryDetailPane.style.width = `${100 - masterPanePercentage}%`;
            }

            async function open() {
                DOM.newImageGalleryModal.style.display = 'flex';
                await _setupFilters();
                // Don't load images automatically - wait for user to enter search criteria
                imageData = [];
                selectedImageIndex = -1;
                selectMode = false;
                selectedImageIds.clear();
                if (DOM.newImageGallerySelectMode) {
                    DOM.newImageGallerySelectMode.checked = false;
                }
                if (DOM.newImageGalleryBulkTags) {
                    DOM.newImageGalleryBulkTags.value = '';
                }
                _updateSelectModeUI();
                _renderThumbnailGrid();
            }

            async function openTaggedImages(tags) {
                await open();
                if (DOM.newImageGalleryTags) {
                    DOM.newImageGalleryTags.value = tags;
                }
                const params = new URLSearchParams();
                params.append('tags', tags);
                try {
                    const response = await fetch('/images/search?' + params.toString());
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    const data = await response.json();
                    imageData = data;
                    _renderThumbnailGrid();
                } catch (error) {
                    console.error('Error loading image data:', error);
                    imageData = [];
                    _renderThumbnailGrid();
                }
            }

            async function openImagesFromDate(year, month) {
                await open();
                if (DOM.newImageGalleryYearFilter) {
                    DOM.newImageGalleryYearFilter.value = year;
                }
                if (DOM.newImageGalleryMonthFilter) {
                    DOM.newImageGalleryMonthFilter.value = month;
                }
                _handleSearch();
            }
            

            function close() {
                DOM.newImageGalleryModal.style.display = 'none';
                selectedImageIndex = -1;
            }

            async function _setupFilters() {
                // Setup year filter - fetch distinct years from API
                try {
                    const response = await fetch('/images/years');
                    if (!response.ok) {
                        throw new Error(`Failed to fetch years: ${response.statusText}`);
                    }
                    const data = await response.json();
                    const distinctYears = data.years || [];
                    
                    // Build years array with "All Years" option first, then distinct years
                    const years = [
                        { value: 0, text: 'All Years' }
                    ];
                    
                    // Add distinct years from database
                    distinctYears.forEach(year => {
                        years.push({ value: year, text: year.toString() });
                    });
                    
                    if (DOM.newImageGalleryYearFilter) {
                        DOM.newImageGalleryYearFilter.innerHTML = '';
                        years.forEach(year => {
                            const option = document.createElement('option');
                            option.value = year.value;
                            option.textContent = year.text;
                            DOM.newImageGalleryYearFilter.appendChild(option);
                        });
                    }
                } catch (error) {
                    console.error('Error loading years:', error);
                    // Fallback to "All Years" option if API call fails
                    if (DOM.newImageGalleryYearFilter) {
                        DOM.newImageGalleryYearFilter.innerHTML = '<option value="0" selected>All Years</option>';
                    }
                }

                // Setup tags datalist - fetch distinct tags from API
                try {
                    const tagsResponse = await fetch('/images/tags');
                    if (!tagsResponse.ok) {
                        throw new Error(`Failed to fetch tags: ${tagsResponse.statusText}`);
                    }
                    const tagsData = await tagsResponse.json();
                    const distinctTags = tagsData.tags || [];
                    
                    // Populate datalist with distinct tags
                    const tagsDatalist = document.getElementById('new-image-gallery-tags-list');
                    if (tagsDatalist) {
                        tagsDatalist.innerHTML = '';
                        distinctTags.forEach(tag => {
                            const option = document.createElement('option');
                            option.value = tag;
                            tagsDatalist.appendChild(option);
                        });
                    }
                } catch (error) {
                    console.error('Error loading tags:', error);
                    // Continue without tags datalist if API call fails
                }

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
                
                if (DOM.newImageGalleryMonthFilter) {
                    DOM.newImageGalleryMonthFilter.innerHTML = '';
                    months.forEach(month => {
                        const option = document.createElement('option');
                        option.value = month.value;
                        option.textContent = month.text;
                        DOM.newImageGalleryMonthFilter.appendChild(option);
                    });
                }
            }

            async function _loadImageData() {
                const params = new URLSearchParams();
                
                // Build query parameters from filter inputs
                if (DOM.newImageGalleryTitle && DOM.newImageGalleryTitle.value.trim()) {
                    params.append('title', DOM.newImageGalleryTitle.value.trim());
                }
                if (DOM.newImageGalleryDescription && DOM.newImageGalleryDescription.value.trim()) {
                    params.append('description', DOM.newImageGalleryDescription.value.trim());
                }
                if (DOM.newImageGalleryTags && DOM.newImageGalleryTags.value.trim()) {
                    params.append('tags', DOM.newImageGalleryTags.value.trim());
                }
                if (DOM.newImageGalleryAuthor && DOM.newImageGalleryAuthor.value.trim()) {
                    params.append('author', DOM.newImageGalleryAuthor.value.trim());
                }
                if (DOM.newImageGallerySource && DOM.newImageGallerySource.value.trim()) {
                    params.append('source', DOM.newImageGallerySource.value.trim());
                }
                if (DOM.newImageGalleryYearFilter && DOM.newImageGalleryYearFilter.value && DOM.newImageGalleryYearFilter.value !== '0') {
                    params.append('year', DOM.newImageGalleryYearFilter.value);
                }
                if (DOM.newImageGalleryMonthFilter && DOM.newImageGalleryMonthFilter.value && DOM.newImageGalleryMonthFilter.value !== '0') {
                    params.append('month', DOM.newImageGalleryMonthFilter.value);
                }
                if (DOM.newImageGalleryRating && DOM.newImageGalleryRating.value) {
                    params.append('rating', DOM.newImageGalleryRating.value);
                }
                if (DOM.newImageGalleryRatingMin && DOM.newImageGalleryRatingMin.value) {
                    params.append('rating_min', DOM.newImageGalleryRatingMin.value);
                }
                if (DOM.newImageGalleryRatingMax && DOM.newImageGalleryRatingMax.value) {
                    params.append('rating_max', DOM.newImageGalleryRatingMax.value);
                }
                if (DOM.newImageGalleryHasGps && DOM.newImageGalleryHasGps.checked) {
                    params.append('has_gps', 'true');
                }
                if (DOM.newImageGalleryProcessed && DOM.newImageGalleryProcessed.checked) {
                    params.append('processed', 'true');
                }

                try {
                    const response = await fetch('/images/search?' + params.toString());
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    const data = await response.json();
                    imageData = data;
                    _renderThumbnailGrid();
                } catch (error) {
                    console.error('Error loading image data:', error);
                    imageData = [];
                    _renderThumbnailGrid();
                }
            }

            function _renderThumbnailGrid() {
                // Reset pagination when rendering new grid
                currentPage = 0;
                hasMoreData = true;
                DOM.newImageGalleryThumbnailGrid.innerHTML = '';

                if (imageData.length === 0) {
                    const noResults = document.createElement('div');
                    noResults.style.textAlign = 'center';
                    noResults.style.padding = '2em';
                    noResults.style.color = '#666';
                    noResults.style.gridColumn = '1 / -1';
                    // Check if we have any search criteria
                    const hasCriteria = _hasSearchCriteria();
                    noResults.textContent = hasCriteria 
                        ? 'No images found matching your criteria' 
                        : 'Enter search criteria above and click Search to find images';
                    DOM.newImageGalleryThumbnailGrid.appendChild(noResults);
                    return;
                }

                _loadMoreThumbnails();
            }

            function _hasSearchCriteria() {
                return (
                    (DOM.newImageGalleryTitle && DOM.newImageGalleryTitle.value.trim()) ||
                    (DOM.newImageGalleryDescription && DOM.newImageGalleryDescription.value.trim()) ||
                    (DOM.newImageGalleryTags && DOM.newImageGalleryTags.value.trim()) ||
                    (DOM.newImageGalleryAuthor && DOM.newImageGalleryAuthor.value.trim()) ||
                    (DOM.newImageGallerySource && DOM.newImageGallerySource.value.trim()) ||
                    (DOM.newImageGalleryYearFilter && DOM.newImageGalleryYearFilter.value && DOM.newImageGalleryYearFilter.value !== '0') ||
                    (DOM.newImageGalleryMonthFilter && DOM.newImageGalleryMonthFilter.value && DOM.newImageGalleryMonthFilter.value !== '0') ||
                    (DOM.newImageGalleryRating && DOM.newImageGalleryRating.value) ||
                    (DOM.newImageGalleryRatingMin && DOM.newImageGalleryRatingMin.value) ||
                    (DOM.newImageGalleryRatingMax && DOM.newImageGalleryRatingMax.value) ||
                    (DOM.newImageGalleryHasGps && DOM.newImageGalleryHasGps.checked) ||
                    (DOM.newImageGalleryProcessed && DOM.newImageGalleryProcessed.checked)
                );
            }

            function _getSourceAbbreviation(source) {
                // Return short abbreviation for source
                const abbreviations = {
                    'Email': 'E',
                    'Facebook Album': 'FB',
                    'Filesystem': 'FS',
                    'Instagram': 'IG',
                    'WhatsApp': 'WA',
                    'iMessage': 'iM'
                };
                return abbreviations[source] || source.substring(0, 2).toUpperCase();
            }

            function _loadMoreThumbnails() {
                if (isLoading || !hasMoreData) return;

                isLoading = true;
                
                const startIndex = currentPage * itemsPerPage;
                const endIndex = startIndex + itemsPerPage;
                const imagesToRender = imageData.slice(startIndex, endIndex);

                if (imagesToRender.length === 0) {
                    hasMoreData = false;
                    isLoading = false;
                    return;
                }
                
                imagesToRender.forEach((image, localIndex) => {
                    const actualIndex = startIndex + localIndex;
                    
                    const thumbnailItem = document.createElement('div');
                    thumbnailItem.className = 'new-image-gallery-thumbnail-item';
                    thumbnailItem.dataset.index = actualIndex;
                    
                    const img = document.createElement('img');
                    img.loading = 'lazy';
                    img.src = `/images/${image.id}?type=metadata&preview=true`;
                    img.alt = image.title || 'Image thumbnail';
                    img.onerror = function() {
                        this.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="150" height="150"%3E%3Crect fill="%23ddd" width="150" height="150"/%3E%3Ctext fill="%23999" font-family="sans-serif" font-size="14" x="50%25" y="50%25" text-anchor="middle" dy=".3em"%3ENo Image%3C/text%3E%3C/svg%3E';
                    };
                    
                    thumbnailItem.appendChild(img);
                    
                    // Add source indicator badge
                    if (image.source) {
                        const sourceBadge = document.createElement('div');
                        sourceBadge.className = 'new-image-gallery-source-badge';
                        sourceBadge.dataset.source = image.source;
                        sourceBadge.textContent = _getSourceAbbreviation(image.source);
                        thumbnailItem.appendChild(sourceBadge);
                    }
                    
                    thumbnailItem.addEventListener('click', () => _selectImage(actualIndex));
                    
                    // Update selection state if in select mode
                    if (selectMode && selectedImageIds.has(image.id)) {
                        thumbnailItem.classList.add('bulk-selected');
                    }
                    
                    DOM.newImageGalleryThumbnailGrid.appendChild(thumbnailItem);
                });

                currentPage++;
                hasMoreData = endIndex < imageData.length;
                isLoading = false;

                // Check if we need to load more to fill the viewport
                // Use setTimeout to allow DOM to update before checking
                setTimeout(() => {
                    if (hasMoreData) {
                        _checkAndLoadMoreIfNeeded();
                        // Add loading indicator if viewport is filled and there's more data
                        const grid = DOM.newImageGalleryThumbnailGrid;
                        if (grid.scrollHeight > grid.clientHeight + 50) {
                            _addLoadingIndicator();
                        }
                    }
                }, 100);
            }

            function _addLoadingIndicator() {
                // Remove existing loading indicator
                const existingIndicator = DOM.newImageGalleryThumbnailGrid.querySelector('.loading-indicator');
                if (existingIndicator) {
                    existingIndicator.remove();
                }

                const loadingIndicator = document.createElement('div');
                loadingIndicator.className = 'loading-indicator';
                loadingIndicator.style.gridColumn = '1 / -1';
                loadingIndicator.style.textAlign = 'center';
                loadingIndicator.style.padding = '1em';
                loadingIndicator.style.color = '#666';
                loadingIndicator.innerHTML = `
                    <div style="display: inline-block; width: 20px; height: 20px; border: 2px solid #f3f3f3; border-top: 2px solid #4a90e2; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                    <div style="margin-top: 0.5em;">Loading more images...</div>
                `;
                DOM.newImageGalleryThumbnailGrid.appendChild(loadingIndicator);
            }

            function _handleThumbnailScroll() {
                const grid = DOM.newImageGalleryThumbnailGrid;
                const { scrollTop, scrollHeight, clientHeight } = grid;
                
                // Load more thumbnails when user scrolls to within 200px of the bottom
                if (scrollTop + clientHeight >= scrollHeight - 200) {
                    _loadMoreThumbnails();
                }
            }

            function _checkAndLoadMoreIfNeeded() {
                // Check if viewport needs more content and load if necessary
                const grid = DOM.newImageGalleryThumbnailGrid;
                if (hasMoreData && grid.scrollHeight <= grid.clientHeight + 50) {
                    // Viewport is not filled enough, load more thumbnails
                    _loadMoreThumbnails();
                }
            }

            async function _selectImage(index) {
                if (index < 0 || index >= imageData.length) return;
                
                const image = imageData[index];
                
                if (selectMode) {
                    // Toggle selection in select mode
                    if (selectedImageIds.has(image.id)) {
                        selectedImageIds.delete(image.id);
                    } else {
                        selectedImageIds.add(image.id);
                    }
                    _updateSelectionUI();
                } else {
                    // Normal mode: open detail modal
                    selectedImageIndex = index;
                    
                    // Update selected state in UI
                    const thumbnails = DOM.newImageGalleryThumbnailGrid.querySelectorAll('.new-image-gallery-thumbnail-item');
                    thumbnails.forEach((thumb, idx) => {
                        const actualIdx = parseInt(thumb.dataset.index);
                        if (actualIdx === index) {
                            thumb.classList.add('selected');
                            thumb.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                        } else {
                            thumb.classList.remove('selected');
                        }
                    });
                    
                    // Open detail modal with full image and metadata
                    Modals.ImageDetailModal.open(image, {
                        allowRedirects: true,
                        onSave: (updatedImage, updateData) => {
                            // Update the image in imageData array
                            const imageIndex = imageData.findIndex(img => img.id === updatedImage.id);
                            if (imageIndex !== -1) {
                                imageData[imageIndex].description = updateData.description;
                                imageData[imageIndex].tags = updateData.tags;
                                imageData[imageIndex].rating = updateData.rating;
                            }
                        },
                        onDelete: (deletedImage) => {
                            // Remove from imageData array
                            imageData = imageData.filter(img => img.id !== deletedImage.id);
                            
                            // Update selected index
                            if (selectedImageIndex >= imageData.length) {
                                selectedImageIndex = -1;
                            }
                            
                            // Refresh thumbnail grid
                            _renderThumbnailGrid();
                            
                            // Remove selected state from thumbnails
                            const thumbnails = DOM.newImageGalleryThumbnailGrid.querySelectorAll('.new-image-gallery-thumbnail-item');
                            thumbnails.forEach(thumb => thumb.classList.remove('selected'));
                        }
                    });
                }
            }
            
            function _updateSelectModeUI() {
                if (DOM.newImageGalleryBulkEditSection) {
                    DOM.newImageGalleryBulkEditSection.style.display = selectMode ? 'block' : 'none';
                }
                _updateSelectionUI();
            }
            
            function _updateSelectionUI() {
                // Update selected count
                if (DOM.newImageGallerySelectedCount) {
                    DOM.newImageGallerySelectedCount.textContent = selectedImageIds.size;
                }
                
                // Enable/disable apply button
                if (DOM.newImageGalleryApplyTagsBtn) {
                    DOM.newImageGalleryApplyTagsBtn.disabled = selectedImageIds.size === 0 || 
                        !DOM.newImageGalleryBulkTags || !DOM.newImageGalleryBulkTags.value.trim();
                }
                
                // Enable/disable delete button
                if (DOM.newImageGalleryDeleteSelectedBtn) {
                    DOM.newImageGalleryDeleteSelectedBtn.disabled = selectedImageIds.size === 0;
                }
                
                // Update thumbnail visual selection state
                const thumbnails = DOM.newImageGalleryThumbnailGrid.querySelectorAll('.new-image-gallery-thumbnail-item');
                thumbnails.forEach((thumb) => {
                    const actualIdx = parseInt(thumb.dataset.index);
                    if (actualIdx >= 0 && actualIdx < imageData.length) {
                        const image = imageData[actualIdx];
                        if (selectedImageIds.has(image.id)) {
                            thumb.classList.add('bulk-selected');
                        } else {
                            thumb.classList.remove('bulk-selected');
                        }
                    }
                });
            }
            
            async function _applyTagsToSelected() {
                if (selectedImageIds.size === 0) return;
                
                const tags = DOM.newImageGalleryBulkTags ? DOM.newImageGalleryBulkTags.value.trim() : '';
                if (!tags) {
                    alert('Please enter tags to apply');
                    return;
                }
                
                const imageIds = Array.from(selectedImageIds);
                
                try {
                    const response = await fetch('/images/bulk-update', {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            image_ids: imageIds,
                            tags: tags
                        })
                    });
                    
                    if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
                    }
                    
                    const result = await response.json();
                    
                    // Update local image data
                    imageIds.forEach(id => {
                        const imageIndex = imageData.findIndex(img => img.id === id);
                        if (imageIndex !== -1) {
                            // Merge tags (append if existing)
                            const existingTags = imageData[imageIndex].tags || '';
                            const newTags = existingTags ? `${existingTags}, ${tags}` : tags;
                            imageData[imageIndex].tags = newTags;
                        }
                    });
                    
                    // Clear selection and tags input
                    selectedImageIds.clear();
                    if (DOM.newImageGalleryBulkTags) {
                        DOM.newImageGalleryBulkTags.value = '';
                    }
                    _updateSelectionUI();
                    
                    alert(`Successfully applied tags to ${result.updated_count} image(s)`);
                } catch (error) {
                    console.error('Error applying tags:', error);
                    alert(`Error applying tags: ${error.message}`);
                }
            }
            
            async function _deleteSelectedImages() {
                if (selectedImageIds.size === 0) return;
                
                const imageIds = Array.from(selectedImageIds);
                const count = imageIds.length;
                
                // Confirm deletion
                if (!confirm(`Are you sure you want to delete ${count} image(s)? This action cannot be undone.`)) {
                    return;
                }
                
                try {
                    const response = await fetch('/images/bulk-delete', {
                        method: 'DELETE',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            image_ids: imageIds
                        })
                    });
                    
                    if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
                    }
                    
                    const result = await response.json();
                    
                    // Remove deleted images from imageData array
                    imageData = imageData.filter(img => !selectedImageIds.has(img.id));
                    
                    // Clear selection
                    selectedImageIds.clear();
                    _updateSelectionUI();
                    
                    // Refresh thumbnail grid
                    _renderThumbnailGrid();
                    
                    // Close detail modal if the deleted image was being viewed
                    const deletedIds = new Set(imageIds);
                    // Note: ImageDetailModal manages its own state, so we just close it
                    if (deletedIds.size > 0 && DOM.newImageGalleryDetailModal) {
                        DOM.newImageGalleryDetailModal.style.display = 'none';
                    }
                    
                    alert(`Successfully deleted ${result.deleted_count} image(s)`);
                } catch (error) {
                    console.error('Error deleting images:', error);
                    alert(`Error deleting images: ${error.message}`);
                }
            }


            function _handleSearch() {
                _loadImageData();
            }

            function _handleClear() {
                if (DOM.newImageGalleryTitle) DOM.newImageGalleryTitle.value = '';
                if (DOM.newImageGalleryDescription) DOM.newImageGalleryDescription.value = '';
                if (DOM.newImageGalleryTags) DOM.newImageGalleryTags.value = '';
                if (DOM.newImageGalleryAuthor) DOM.newImageGalleryAuthor.value = '';
                if (DOM.newImageGallerySource) DOM.newImageGallerySource.value = '';
                if (DOM.newImageGalleryYearFilter) DOM.newImageGalleryYearFilter.value = 0;
                if (DOM.newImageGalleryMonthFilter) DOM.newImageGalleryMonthFilter.value = 0;
                if (DOM.newImageGalleryRating) DOM.newImageGalleryRating.value = '';
                if (DOM.newImageGalleryRatingMin) DOM.newImageGalleryRatingMin.value = '';
                if (DOM.newImageGalleryRatingMax) DOM.newImageGalleryRatingMax.value = '';
                if (DOM.newImageGalleryHasGps) DOM.newImageGalleryHasGps.checked = false;
                if (DOM.newImageGalleryProcessed) DOM.newImageGalleryProcessed.checked = false;
                
                selectedImageIndex = -1;
                selectedImageIds.clear();
                _updateSelectionUI();
                imageData = [];
                _renderThumbnailGrid();
            }


            return { init, open, close,openTaggedImages, openImagesFromDate };
        })(),

        ImageDetailModal: (() => {
            let currentImageInModal = null;
            let originalImageData = null;
            let starRatingListenerAttached = false;
            let onSaveCallback = null;
            let onDeleteCallback = null;
            let allowRedirects = true;

            function formatDate(year, month) {
                if (!year && !month) return 'No Date';
                const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
                    'July', 'August', 'September', 'October', 'November', 'December'];
                if (year && month) {
                    return `${monthNames[month - 1]} ${year}`;
                } else if (year) {
                    return year.toString();
                } else if (month) {
                    return monthNames[month - 1];
                }
                return 'No Date';
            }

            function formatDateTime(dateTime) {
                if (!dateTime) return 'N/A';
                try {
                    const date = new Date(dateTime);
                    if (isNaN(date.getTime())) return 'N/A';
                    
                    const day = String(date.getDate()).padStart(2, '0');
                    const month = String(date.getMonth() + 1).padStart(2, '0');
                    const year = date.getFullYear();
                    const hours = String(date.getHours()).padStart(2, '0');
                    const minutes = String(date.getMinutes()).padStart(2, '0');
                    
                    return `${day}/${month}/${year} ${hours}:${minutes}`;
                } catch (e) {
                    return dateTime.toString();
                }
            }

            function _setupStarRating(rating) {
                if (!DOM.newImageDetailRatingContainer || !DOM.newImageDetailRatingEdit) {
                    return;
                }
                
                const stars = DOM.newImageDetailRatingContainer.querySelectorAll('.star');
                if (!stars || stars.length === 0) {
                    return;
                }
                
                // Convert rating to number - handle various input types
                let currentRating = 0;
                if (rating !== null && rating !== undefined && rating !== '') {
                    // Handle both string and number inputs
                    const parsed = typeof rating === 'number' ? rating : parseInt(String(rating), 10);
                    if (!isNaN(parsed) && parsed >= 1 && parsed <= 5) {
                        currentRating = parsed;
                    }
                }
                
                // Set hidden input value
                DOM.newImageDetailRatingEdit.value = currentRating > 0 ? currentRating : '';
                
                // Update star display - clear all first, then add active to stars up to rating
                stars.forEach((star, index) => {
                    const starRating = index + 1;
                    // Remove active class first
                    star.classList.remove('active');
                    // Add active class if this star should be active
                    if (starRating <= currentRating) {
                        star.classList.add('active');
                    }
                });
                
                
                // Set up click handler using event delegation (only once)
                if (!starRatingListenerAttached) {
                    DOM.newImageDetailRatingContainer.addEventListener('click', (e) => {
                        const star = e.target.closest('.star');
                        if (!star) return;
                        
                        e.stopPropagation();
                        const starRating = parseInt(star.getAttribute('data-rating'), 10);
                        if (isNaN(starRating) || starRating < 1 || starRating > 5) return;
                        
                        // Update hidden input
                        DOM.newImageDetailRatingEdit.value = starRating;
                        
                        // Update all stars - clear all first, then add active to stars up to clicked rating
                        const allStars = DOM.newImageDetailRatingContainer.querySelectorAll('.star');
                        allStars.forEach((s) => {
                            s.classList.remove('active');
                            const sRating = parseInt(s.getAttribute('data-rating'), 10);
                            if (sRating <= starRating) {
                                s.classList.add('active');
                            }
                        });
                        
                        
                        _checkForChanges();
                    });
                    starRatingListenerAttached = true;
                }
            }
            
            function _setupChangeTracking() {
                // Remove existing listeners to avoid duplicates
                const descriptionEdit = DOM.newImageDetailDescriptionEdit;
                const tagsEdit = DOM.newImageDetailTagsEdit;
                
                if (descriptionEdit) {
                    descriptionEdit.removeEventListener('input', _checkForChanges);
                    descriptionEdit.addEventListener('input', _checkForChanges);
                }
                
                if (tagsEdit) {
                    tagsEdit.removeEventListener('input', _checkForChanges);
                    tagsEdit.addEventListener('input', _checkForChanges);
                }
            }
            
            function _checkForChanges() {
                if (!originalImageData || !currentImageInModal) return;
                
                const currentDescription = DOM.newImageDetailDescriptionEdit ? DOM.newImageDetailDescriptionEdit.value.trim() : '';
                const currentTags = DOM.newImageDetailTagsEdit ? DOM.newImageDetailTagsEdit.value.trim() : '';
                const currentRating = DOM.newImageDetailRatingEdit ? parseInt(DOM.newImageDetailRatingEdit.value) || null : null;
                
                const hasChanges = 
                    currentDescription !== (originalImageData.description || '') ||
                    currentTags !== (originalImageData.tags || '') ||
                    currentRating !== (originalImageData.rating || null);
                
                if (DOM.newImageGallerySaveBtn) {
                    DOM.newImageGallerySaveBtn.disabled = !hasChanges;
                }
            }
            
            async function saveChanges() {
                if (!currentImageInModal) return;
                
                const imageId = currentImageInModal.id;
                const description = DOM.newImageDetailDescriptionEdit ? DOM.newImageDetailDescriptionEdit.value.trim() : null;
                const tags = DOM.newImageDetailTagsEdit ? DOM.newImageDetailTagsEdit.value.trim() : null;
                const rating = DOM.newImageDetailRatingEdit ? parseInt(DOM.newImageDetailRatingEdit.value) || null : null;
                
                const updateData = {};
                if (description !== null) updateData.description = description || null;
                if (tags !== null) updateData.tags = tags || null;
                if (rating !== null) updateData.rating = rating;
                
                try {
                    const response = await fetch(`/images/${imageId}`, {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(updateData)
                    });
                    
                    if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
                    }
                    
                    // Update currentImageInModal
                    currentImageInModal.description = description;
                    currentImageInModal.tags = tags;
                    currentImageInModal.rating = rating;
                    
                    // Update original data
                    originalImageData = {
                        description: description || '',
                        tags: tags || '',
                        rating: rating || null
                    };
                    
                    // Disable save button
                    if (DOM.newImageGallerySaveBtn) {
                        DOM.newImageGallerySaveBtn.disabled = true;
                    }
                    
                    // Call callback if provided
                    if (onSaveCallback) {
                        onSaveCallback(currentImageInModal, updateData);
                    }
                    
                    alert('Image metadata updated successfully');
                } catch (error) {
                    console.error('Error updating image:', error);
                    alert(`Error updating image: ${error.message}`);
                }
            }

            async function deleteImage() {
                if (!currentImageInModal) return;
                
                const imageId = currentImageInModal.id;
                const imageTitle = currentImageInModal.title || 'Image';
                
                // Confirm deletion
                if (!confirm(`Are you sure you want to delete "${imageTitle}"? This action cannot be undone.`)) {
                    return;
                }
                
                try {
                    const response = await fetch(`/images/${imageId}`, {
                        method: 'DELETE'
                    });
                    
                    if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
                    }
                    
                    // Close the modal
                    DOM.newImageGalleryDetailModal.style.display = 'none';
                    const deletedImage = currentImageInModal;
                    currentImageInModal = null;
                    originalImageData = null;
                    
                    // Call callback if provided
                    if (onDeleteCallback) {
                        onDeleteCallback(deletedImage);
                    }
                    
                    alert(`Successfully deleted image: ${imageTitle}`);
                } catch (error) {
                    console.error('Error deleting image:', error);
                    alert(`Error deleting image: ${error.message}`);
                }
            }

            function open(image, options = {}) {
                // Extract options
                allowRedirects = options.allowRedirects !== undefined ? options.allowRedirects : true;
                onSaveCallback = options.onSave || null;
                onDeleteCallback = options.onDelete || null;

                // Check if source is Email - if so, navigate to Email Gallery instead (if redirects allowed)
                if (allowRedirects && image.source === "Email" && image.source_reference) {
                    const emailId = parseInt(image.source_reference);
                    
                    if (!isNaN(emailId)) {
                        // Close Image Gallery modals
                        if (DOM.newImageGalleryModal) DOM.newImageGalleryModal.style.display = 'none';
                        if (DOM.newImageGalleryDetailModal) DOM.newImageGalleryDetailModal.style.display = 'none';
                        
                        // Open Email Gallery and select the email
                        Modals.EmailGallery.openAndSelectEmail(emailId);
                        return; // Don't open image detail modal
                    }
                }
                
                // Check if source is Facebook Album - if so, navigate to Facebook Albums Gallery instead (if redirects allowed)
                if (allowRedirects && image.source === "Facebook Album" && image.source_reference) {
                    const albumId = image.source_reference;
                    
                    if (albumId) {
                        // Close Image Gallery modals
                        if (DOM.newImageGalleryModal) DOM.newImageGalleryModal.style.display = 'none';
                        if (DOM.newImageGalleryDetailModal) DOM.newImageGalleryDetailModal.style.display = 'none';
                        
                        // Open Facebook Albums Gallery and select the album
                        Modals.FBAlbums.openAndSelectAlbum(albumId);
                        return; // Don't open image detail modal
                    }
                }


                
                currentImageInModal = image;
                
                // Store original values for change detection
                originalImageData = {
                    description: image.description || '',
                    tags: image.tags || '',
                    rating: image.rating || null
                };
                
                // Set image source
                DOM.newImageGalleryDetailImage.src = `/images/${image.id}?type=metadata&convert_heic_to_jpg=true`;
                DOM.newImageGalleryDetailImage.alt = image.title || 'Image';
                
                // Show delete and save buttons
                if (DOM.newImageGalleryDeleteBtn) {
                    DOM.newImageGalleryDeleteBtn.style.display = 'inline-block';
                }
                if (DOM.newImageGallerySaveBtn) {
                    DOM.newImageGallerySaveBtn.style.display = 'inline-block';
                    DOM.newImageGallerySaveBtn.disabled = true;
                }
                
                // Populate all metadata fields
                DOM.newImageDetailTitle.textContent = image.title || 'N/A';
                
                // Populate editable fields
                if (DOM.newImageDetailDescriptionEdit) {
                    DOM.newImageDetailDescriptionEdit.value = image.description || '';
                }
                if (DOM.newImageDetailTagsEdit) {
                    DOM.newImageDetailTagsEdit.value = image.tags || '';
                }
                
                // Set up star rating
                _setupStarRating(image.rating || null);
                
                DOM.newImageDetailAuthor.textContent = image.author || 'N/A';
                DOM.newImageDetailCategories.textContent = image.categories || 'N/A';
                DOM.newImageDetailNotes.textContent = image.notes || 'N/A';
                DOM.newImageDetailDate.textContent = formatDate(image.year, image.month);
                DOM.newImageDetailImageType.textContent = image.media_type || image.image_type || 'N/A';
                
                // Source: Show button if not "Filesystem", otherwise show text
                const sourceValue = image.source || 'N/A';
                DOM.newImageDetailSource.innerHTML = '';
                if (sourceValue && sourceValue !== 'N/A' && sourceValue.toLowerCase() !== 'filesystem') {
                    const openSourceButton = document.createElement('button');
                    openSourceButton.type = 'button';
                    openSourceButton.className = 'modal-btn modal-btn-secondary';
                    openSourceButton.style.cssText = 'padding: 0.3em 0.8em; font-size: 0.85em;';
                    openSourceButton.textContent = 'Open Source ('+sourceValue+')';
                    openSourceButton.onclick = function(e) {


                        e.preventDefault();
                        e.stopPropagation();
                        
                        // Handle email-attachment source
                        if (sourceValue.toLowerCase() === 'email_attachment' || sourceValue.toLowerCase() === 'email') {
                            if (image.source_reference) {
                                const emailId = parseInt(image.source_reference);
                                if (!isNaN(emailId)) {
                                    // Open email gallery and select the email
                                    Modals.ImageDetailModal.close();
                                    Modals.EmailGallery.openAndSelectEmail(emailId);
                                } else {
                                    console.error('Invalid email ID in source_reference:', image.source_reference);
                                    alert('Unable to open email: Invalid email ID');
                                }
                            } else {
                                console.error('No source_reference found for email attachment');
                                alert('Unable to open email: No email reference found');
                            }
                        } else if (sourceValue.toLowerCase() === 'message_attachment' || sourceValue.toLowerCase() === 'whatsapp' || sourceValue.toLowerCase() === 'facebook') {
                            //Open the SMS Messages modal and select the conversation
                            Modals.NewImageGallery.close();
                            Modals.ImageDetailModal.close();
                            Modals.SMSMessages.openAndSelectConversation(image.source_reference);
                        } else if (sourceValue.toLowerCase() === 'facebook_album') {
                            //Open the Facebook Albums modal and select the album
                            Modals.NewImageGallery.close();
                            Modals.ImageDetailModal.close();
                            Modals.FBAlbums.openAndSelectAlbum(image.source_reference);
                        }
                        // Add other source types here as needed
                    };
                    DOM.newImageDetailSource.appendChild(openSourceButton);
                } else {
                    DOM.newImageDetailSource.textContent = sourceValue;
                }
                
                DOM.newImageDetailSourceReference.textContent = image.source_reference || 'N/A';
                DOM.newImageDetailRegion.textContent = image.region || 'N/A';
                DOM.newImageDetailAvailableForTask.textContent = image.available_for_task ? 'Yes' : 'No';
                DOM.newImageDetailProcessed.textContent = image.processed ? 'Yes' : 'No';
                DOM.newImageDetailCreatedAt.textContent = formatDateTime(image.created_at);
                DOM.newImageDetailUpdatedAt.textContent = formatDateTime(image.updated_at);
                
                // GPS Location
            
                if (image.has_gps && (image.latitude || image.longitude)) {
                    let gpsText = '';
                    if (image.latitude && image.longitude) {
                        gpsText = `${image.latitude.toFixed(6)}, ${image.longitude.toFixed(6)}`;
                        
                        // Create Google Maps URL
                        const googleMapsUrl = `https://www.google.com/maps?q=${image.latitude},${image.longitude}`;
                        
                        // Add button to open Google Maps in new tab
                        const openMapsButton = document.createElement('button');
                        openMapsButton.type = 'button';
                        openMapsButton.className = 'modal-btn modal-btn-secondary';
                        openMapsButton.style.cssText = 'margin-left: 10px; padding: 0.3em 0.8em; font-size: 0.85em; display: inline-flex; align-items: center; gap: 0.3em;';
                        openMapsButton.innerHTML = '<i class="fas fa-map-marker-alt"></i> Open in Google Maps';
                        openMapsButton.onclick = function(e) {
                            e.preventDefault();
                            e.stopPropagation();
                            window.open(googleMapsUrl, '_blank');
                        };
                        
                        // Clear existing content and add coordinates and button
                        DOM.newImageDetailGps.innerHTML = '';
                        DOM.newImageDetailGps.appendChild(document.createTextNode(gpsText));
                        DOM.newImageDetailGps.appendChild(openMapsButton);
                    } else {
                        DOM.newImageDetailGps.textContent = 'GPS data available';
                    }
                    DOM.newImageDetailGpsRow.style.display = 'flex';
                } else {
                    DOM.newImageDetailGpsRow.style.display = 'none';
                }
                
                // Altitude
                if (image.altitude !== null && image.altitude !== undefined) {
                    DOM.newImageDetailAltitude.textContent = `${image.altitude.toFixed(2)} meters`;
                    DOM.newImageDetailAltitudeRow.style.display = 'flex';
                } else {
                    DOM.newImageDetailAltitudeRow.style.display = 'none';
                }
                
                // Set up change tracking
                _setupChangeTracking();
                
                // Show modal
                DOM.newImageGalleryDetailModal.style.display = 'flex';
            }

            function close() {
                if (DOM.newImageGalleryDetailModal) {
                    DOM.newImageGalleryDetailModal.style.display = 'none';
                }
                currentImageInModal = null;
                originalImageData = null;
                if (DOM.newImageGallerySaveBtn) {
                    DOM.newImageGallerySaveBtn.disabled = true;
                }
            }

            function init() {
                // Close detail modal handler
                if (DOM.closeNewImageGalleryDetailModalBtn) {
                    DOM.closeNewImageGalleryDetailModalBtn.addEventListener('click', close);
                }
                
                // Close modal when clicking outside
                if (DOM.newImageGalleryDetailModal) {
                    DOM.newImageGalleryDetailModal.addEventListener('click', (e) => {
                        if (e.target === DOM.newImageGalleryDetailModal) {
                            close();
                        }
                    });
                }
                
                // Delete button handler
                if (DOM.newImageGalleryDeleteBtn) {
                    DOM.newImageGalleryDeleteBtn.addEventListener('click', async (e) => {
                        e.stopPropagation();
                        await deleteImage();
                    });
                }
                
                // Save button handler
                if (DOM.newImageGallerySaveBtn) {
                    DOM.newImageGallerySaveBtn.addEventListener('click', async (e) => {
                        e.stopPropagation();
                        await saveChanges();
                    });
                }
            }

            return { init, open, close };
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

        ConversationSummary: (() => {
            let currentChatSession = null;

            function open(chatSession) {
                currentChatSession = chatSession;
                const modal = document.getElementById('conversation-summary-modal');
                const progressDiv = document.getElementById('conversation-summary-progress');
                const contentDiv = document.getElementById('conversation-summary-content');
                const errorDiv = document.getElementById('conversation-summary-error');
                const progressText = document.getElementById('conversation-summary-progress-text');

                if (!modal) {
                    console.error('Conversation summary modal not found');
                    return;
                }

                // Reset UI and show waiting dialog immediately
                contentDiv.innerHTML = '';
                errorDiv.style.display = 'none';
                errorDiv.innerHTML = '';
                progressDiv.style.display = 'flex';
                progressText.textContent = 'Generating summary... Please wait.';
                modal.style.display = 'flex';

                // Encode chat session for URL
                const encodedSession = encodeURIComponent(chatSession);

                // Use requestAnimationFrame to ensure modal is visible before starting fetch
                requestAnimationFrame(() => {
                    // Call summarize endpoint synchronously
                    fetch(`/imessages/conversation/${encodedSession}/summarize`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    })
                    .then(response => {
                        if (!response.ok) {
                            return response.json().then(err => {
                                const errorMsg = err.detail || 'Failed to generate summary';
                                throw new Error(errorMsg);
                            }).catch(() => {
                                // If JSON parsing fails, use status text
                                throw new Error(`Server error: ${response.status} ${response.statusText}`);
                            });
                        }
                        return response.json();
                    })
                    .then(data => {
                        // Display summary
                        if (data.status === 'completed' && data.summary) {
                            displaySummary(data.summary);
                        } else {
                            displayError('Unexpected response format');
                        }
                    })
                    .catch(error => {
                        let errorMessage = 'Failed to generate summary';
                        
                        if (error.message) {
                            errorMessage = error.message;
                        } else if (error instanceof TypeError && error.message.includes('fetch')) {
                            errorMessage = 'Network error: Unable to connect to server. Please check your connection.';
                        } else if (error.name === 'NetworkError' || error.message.includes('network')) {
                            errorMessage = 'Network error: Unable to connect to server. Please check your connection.';
                        }
                        
                        displayError(errorMessage);
                    });
                });
            }

            function openForEmailThread(chatSession) {
                currentChatSession = chatSession;
                const modal = document.getElementById('conversation-summary-modal');
                const progressDiv = document.getElementById('conversation-summary-progress');
                const contentDiv = document.getElementById('conversation-summary-content');
                const errorDiv = document.getElementById('conversation-summary-error');
                const progressText = document.getElementById('conversation-summary-progress-text');

                if (!modal) {
                    console.error('Conversation summary modal not found');
                    return;
                }

                // Reset UI and show waiting dialog immediately
                contentDiv.innerHTML = '';
                errorDiv.style.display = 'none';
                errorDiv.innerHTML = '';
                progressDiv.style.display = 'flex';
                progressText.textContent = 'Generating summary... Please wait.';
                modal.style.display = 'flex';

                // Encode chat session for URL
                const encodedSession = encodeURIComponent(chatSession);

                // Use requestAnimationFrame to ensure modal is visible before starting fetch
                requestAnimationFrame(() => {
                    // Call summarize endpoint synchronously
                    fetch(`/emails/thread/${encodedSession}/summarize`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    })
                    .then(response => {
                        if (!response.ok) {
                            return response.json().then(err => {
                                const errorMsg = err.detail || 'Failed to generate summary';
                                throw new Error(errorMsg);
                            }).catch(() => {
                                // If JSON parsing fails, use status text
                                throw new Error(`Server error: ${response.status} ${response.statusText}`);
                            });
                        }
                        return response.json();
                    })
                    .then(data => {
                        // Display summary
                        if (data.status === 'completed' && data.summary) {
                            displaySummary(data.summary);
                        } else {
                            displayError('Unexpected response format');
                        }
                    })
                    .catch(error => {
                        let errorMessage = 'Failed to generate summary';
                        
                        if (error.message) {
                            errorMessage = error.message;
                        } else if (error instanceof TypeError && error.message.includes('fetch')) {
                            errorMessage = 'Network error: Unable to connect to server. Please check your connection.';
                        } else if (error.name === 'NetworkError' || error.message.includes('network')) {
                            errorMessage = 'Network error: Unable to connect to server. Please check your connection.';
                        }
                        
                        displayError(errorMessage);
                    });
                });
            }

            function displaySummary(summary) {
                const progressDiv = document.getElementById('conversation-summary-progress');
                const contentDiv = document.getElementById('conversation-summary-content');
                const errorDiv = document.getElementById('conversation-summary-error');

                if (!contentDiv) return;

                // Hide progress
                if (progressDiv) {
                    progressDiv.style.display = 'none';
                }

                // Hide error
                if (errorDiv) {
                    errorDiv.style.display = 'none';
                }

                // Display summary (support markdown-like formatting)
                contentDiv.innerHTML = formatSummaryText(summary);
            }

            function formatSummaryText(text) {
                if (!text) return '<p>No summary available.</p>';

                // Check if marked is available
                if (typeof marked !== 'undefined') {
                    try {
                        // Parse and render Markdown
                        const html = marked.parse(text);
                        
                        // Sanitize HTML if DOMPurify is available
                        if (typeof DOMPurify !== 'undefined') {
                            return DOMPurify.sanitize(html);
                        }
                        
                        return html;
                    } catch (error) {
                        console.error('Error rendering markdown:', error);
                        // Fallback to plain text if markdown parsing fails
                        return formatSummaryTextPlain(text);
                    }
                } else {
                    // Fallback if marked is not available
                    console.warn('marked.js not available, using plain text formatting');
                    return formatSummaryTextPlain(text);
                }
            }

            function formatSummaryTextPlain(text) {
                // Escape HTML first
                const escaped = text
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;');

                // Convert line breaks to paragraphs
                const paragraphs = escaped.split(/\n\n+/).filter(p => p.trim());
                return paragraphs.map(p => `<p>${p.replace(/\n/g, '<br>')}</p>`).join('');
            }

            function displayError(errorMessage) {
                const progressDiv = document.getElementById('conversation-summary-progress');
                const errorDiv = document.getElementById('conversation-summary-error');
                const contentDiv = document.getElementById('conversation-summary-content');

                if (!errorDiv) return;

                // Hide progress
                if (progressDiv) {
                    progressDiv.style.display = 'none';
                }

                // Clear content
                if (contentDiv) {
                    contentDiv.innerHTML = '';
                }

                // Display error
                errorDiv.style.display = 'block';
                errorDiv.innerHTML = `<strong>Error:</strong> ${escapeHtml(errorMessage)}`;
            }

            function escapeHtml(text) {
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }

            function close() {
                // Hide modal
                const modal = document.getElementById('conversation-summary-modal');
                if (modal) {
                    modal.style.display = 'none';
                }

                currentChatSession = null;
            }

            function init() {
                const closeBtn = document.getElementById('close-conversation-summary-modal');
                const modal = document.getElementById('conversation-summary-modal');

                if (closeBtn) {
                    closeBtn.addEventListener('click', () => {
                        close();
                    });
                }

                // Close modal when clicking outside
                if (modal) {
                    modal.addEventListener('click', (e) => {
                        if (e.target === modal) {
                            close();
                        }
                    });
                }
            }

            return { init, open, openForEmailThread, close, displaySummary, displayError };
        })(),

        SMSMessages: (() => {
            let chatSessions = [];
            let contactsSessions = [];
            let groupsSessions = [];
            let otherSessions = [];
            let filteredSessions = [];
            let originalChatData = null;
            let currentSession = null;
            let messageTypeFilters = {
                imessage: true,
                sms: true,
                whatsapp: true,
                facebook: true,
                instagram: true,
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
                    // Keep categories separate
                    contactsSessions = data.contacts || [];
                    groupsSessions = data.groups || [];
                    otherSessions = data.other || [];
                    // Combine for backward compatibility with search
                    chatSessions = [
                        ...contactsSessions,
                        ...groupsSessions,
                        ...otherSessions
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

                // Helper function to filter sessions by message type
                function filterByMessageType(sessions) {
                    return sessions.filter(session => {
                        const messageType = session.message_type;
                        
                        // If message type is not defined, don't show it
                        if (!messageType) {
                            return false;
                        }
                        
                        // If it's a mixed conversation, show it if ANY individual type is selected OR if mixed is selected
                        if (messageType === 'mixed') {
                            return messageTypeFilters.mixed === true || 
                                   messageTypeFilters.imessage === true || 
                                   messageTypeFilters.sms === true || 
                                   messageTypeFilters.whatsapp === true || 
                                   messageTypeFilters.facebook === true ||
                                   messageTypeFilters.instagram === true;
                        }
                        
                        // For other types, check if the filter is enabled
                        // Strict boolean check since we're setting boolean values
                        return messageTypeFilters[messageType] === true;
                    });
                }

                // Filter each category separately by message type
                // Also filter by search if filteredSessions is different from chatSessions
                // Create a Set of chat_session values from filteredSessions for efficient lookup
                const filteredSet = new Set(filteredSessions.map(s => s.chat_session));
                const isSearchActive = filteredSessions.length !== chatSessions.length;
                
                let filteredContacts = contactsSessions;
                let filteredGroups = groupsSessions;
                let filteredOther = otherSessions;
                
                if (isSearchActive) {
                    // If search is active, filter each category by what's in filteredSessions
                    filteredContacts = contactsSessions.filter(s => filteredSet.has(s.chat_session));
                    filteredGroups = groupsSessions.filter(s => filteredSet.has(s.chat_session));
                    filteredOther = otherSessions.filter(s => filteredSet.has(s.chat_session));
                }
                
                // Apply message type filter to each category
                const typeFilteredContacts = filterByMessageType(filteredContacts);
                const typeFilteredGroups = filterByMessageType(filteredGroups);
                const typeFilteredOther = filterByMessageType(filteredOther);

                const totalFiltered = typeFilteredContacts.length + typeFilteredGroups.length + typeFilteredOther.length;
                
                if (totalFiltered === 0) {
                    listContainer.innerHTML = '<div style="text-align: center; padding: 2rem; color: #666;">No conversations found</div>';
                    return;
                }

                listContainer.innerHTML = '';
                
                // Render Contacts section
                if (typeFilteredContacts.length > 0) {
                    const categoryHeader = document.createElement('div');
                    categoryHeader.className = 'sms-chat-category-header';
                    categoryHeader.textContent = 'Contacts';
                    categoryHeader.style.cssText = 'padding: 12px 16px; font-weight: 600; font-size: 13px; color: #233366; background-color: #e9ecef; border-bottom: 1px solid #dee2e6; text-transform: uppercase; letter-spacing: 0.5px;';
                    listContainer.appendChild(categoryHeader);
                    
                    typeFilteredContacts.forEach(session => {
                        renderChatSessionItem(session, listContainer);
                    });
                }
                
                // Render Group Chats section
                if (typeFilteredGroups.length > 0) {
                    const categoryHeader = document.createElement('div');
                    categoryHeader.className = 'sms-chat-category-header';
                    categoryHeader.textContent = 'Group Chats';
                    const hasPreviousSection = typeFilteredContacts.length > 0;
                    categoryHeader.style.cssText = 'padding: 12px 16px; font-weight: 600; font-size: 13px; color: #233366; background-color: #e9ecef; border-bottom: 1px solid #dee2e6; border-top: 1px solid #dee2e6; margin-top: ' + (hasPreviousSection ? '8px' : '0') + '; text-transform: uppercase; letter-spacing: 0.5px;';
                    listContainer.appendChild(categoryHeader);
                    
                    typeFilteredGroups.forEach(session => {
                        renderChatSessionItem(session, listContainer);
                    });
                }
                
                // Render Other section
                if (typeFilteredOther.length > 0) {
                    const categoryHeader = document.createElement('div');
                    categoryHeader.className = 'sms-chat-category-header';
                    categoryHeader.textContent = 'Other';
                    const hasPreviousSection = typeFilteredContacts.length > 0 || typeFilteredGroups.length > 0;
                    categoryHeader.style.cssText = 'padding: 12px 16px; font-weight: 600; font-size: 13px; color: #233366; background-color: #e9ecef; border-bottom: 1px solid #dee2e6; border-top: 1px solid #dee2e6; margin-top: ' + (hasPreviousSection ? '8px' : '0') + '; text-transform: uppercase; letter-spacing: 0.5px;';
                    listContainer.appendChild(categoryHeader);
                    
                    typeFilteredOther.forEach(session => {
                        renderChatSessionItem(session, listContainer);
                    });
                }
            }

            function renderChatSessionItem(session, listContainer) {
                    const item = document.createElement('div');
                    item.className = 'sms-chat-session-item';
                    item.dataset.session = session.chat_session;
                    
                    // Profile picture/avatar
                    const avatar = document.createElement('div');
                    avatar.className = 'sms-chat-session-avatar';
                    const initials = (session.chat_session || 'U').substring(0, 2).toUpperCase();
                    avatar.textContent = initials;
                    item.appendChild(avatar);
                    
                    // Content container
                    const content = document.createElement('div');
                    content.className = 'sms-chat-session-content';
                    
                    // Header with name and time
                    const header = document.createElement('div');
                    header.className = 'sms-chat-session-header';
                    
                    const nameSpan = document.createElement('span');
                    nameSpan.className = 'sms-chat-session-name';
                    
                    // Message type icon
                    const messageTypeIcon = document.createElement('i');
                    if (session.message_type === 'imessage') {
                        messageTypeIcon.className = 'fab fa-apple';
                        messageTypeIcon.title = 'iMessage';
                        messageTypeIcon.style.marginRight = '6px';
                        messageTypeIcon.style.color = '#007AFF';
                        messageTypeIcon.style.fontSize = '14px';
                    } else if (session.message_type === 'sms') {
                        messageTypeIcon.className = 'fas fa-comment';
                        messageTypeIcon.title = 'SMS';
                        messageTypeIcon.style.marginRight = '6px';
                        messageTypeIcon.style.color = '#34C759';
                        messageTypeIcon.style.fontSize = '14px';
                    } else if (session.message_type === 'whatsapp') {
                        messageTypeIcon.className = 'fab fa-whatsapp';
                        messageTypeIcon.title = 'WhatsApp';
                        messageTypeIcon.style.marginRight = '6px';
                        messageTypeIcon.style.color = '#25D366';
                        messageTypeIcon.style.fontSize = '14px';
                    } else if (session.message_type === 'facebook') {
                        messageTypeIcon.className = 'fab fa-facebook-messenger';
                        messageTypeIcon.title = 'Facebook Messenger';
                        messageTypeIcon.style.marginRight = '6px';
                        messageTypeIcon.style.color = '#0084FF';
                        messageTypeIcon.style.fontSize = '14px';
                    } else if (session.message_type === 'instagram') {
                        messageTypeIcon.className = 'fab fa-instagram';
                        messageTypeIcon.title = 'Instagram';
                        messageTypeIcon.style.marginRight = '6px';
                        messageTypeIcon.style.color = '#E4405F';
                        messageTypeIcon.style.fontSize = '14px';
                    } else if (session.message_type === 'mixed') {
                        messageTypeIcon.className = 'fas fa-comments';
                        messageTypeIcon.title = 'Mixed';
                        messageTypeIcon.style.marginRight = '6px';
                        messageTypeIcon.style.color = '#FF9500';
                        messageTypeIcon.style.fontSize = '14px';
                    }
                    nameSpan.appendChild(messageTypeIcon);
                    
                    const nameText = document.createTextNode(session.chat_session || 'Unknown');
                    nameSpan.appendChild(nameText);
                    
                    header.appendChild(nameSpan);
                    
                    // Remove time display from master pane - not showing anything
                    const timeSpan = document.createElement('span');
                    timeSpan.className = 'sms-chat-session-time';
                    timeSpan.textContent = '';
                    header.appendChild(timeSpan);
                    
                    content.appendChild(header);
                    
                    // Preview with attachment indicator
                    const preview = document.createElement('div');
                    preview.className = 'sms-chat-session-preview';
                    
                    const previewText = document.createElement('span');
                    previewText.className = 'sms-chat-session-preview-text';
                    
                    // Attachment indicator
                    if (session.has_attachments) {
                        const attachmentIcon = document.createElement('i');
                        attachmentIcon.className = 'fas fa-paperclip';
                        attachmentIcon.style.color = '#667781';
                        attachmentIcon.style.fontSize = '12px';
                        attachmentIcon.style.marginRight = '4px';
                        previewText.appendChild(attachmentIcon);
                    }
                    
                    const previewTextNode = document.createTextNode(`${session.message_count || 0} message${session.message_count !== 1 ? 's' : ''}`);
                    previewText.appendChild(previewTextNode);
                    
                    preview.appendChild(previewText);
                    
                    // Unread count badge
                    if (session.message_count > 0) {
                        const countSpan = document.createElement('span');
                        countSpan.className = 'sms-chat-session-count';
                        countSpan.textContent = session.message_count > 99 ? '99+' : session.message_count;
                        preview.appendChild(countSpan);
                    }
                    
                    content.appendChild(preview);
                    item.appendChild(content);
                    
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
                        } else if (messageType === 'facebook') {
                            icon.className = 'fab fa-facebook-messenger';
                            icon.title = 'Facebook Messenger';
                            icon.style.color = '#0084FF';
                        } else if (messageType === 'instagram') {
                            icon.className = 'fab fa-instagram';
                            icon.title = 'Instagram';
                            icon.style.color = '#E4405F';
                        } else if (messageType === 'mixed') {
                            icon.className = 'fas fa-comments';
                            icon.title = 'Mixed (SMS, iMessage, WhatsApp, Facebook Messenger & Instagram)';
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

                messages.forEach((message, index) => {
                    const messageDiv = document.createElement('div');
                    const isIncoming = message.type === 'Incoming';
                    messageDiv.className = `sms-message ${isIncoming ? 'incoming' : 'outgoing'}`;
                    
                    // Add ID to message div for scrolling to specific messages
                    if (message.id) {
                        messageDiv.id = `message-${message.id}`;
                    }
                    
                    // Add spacing between message groups
                    if (index > 0) {
                        const prevMessage = messages[index - 1];
                        const timeDiff = new Date(message.message_date) - new Date(prevMessage.message_date);
                        const minutesDiff = timeDiff / (1000 * 60);
                        if (minutesDiff > 5 || prevMessage.type !== message.type) {
                            messageDiv.style.marginTop = '10px';
                        }
                    }

                    const bubble = document.createElement('div');
                    bubble.className = 'sms-message-bubble';

                    // Header with sender (for incoming) and date
                    if (isIncoming) {
                        const header = document.createElement('div');
                        header.className = 'sms-message-header';
                        
                        // Service type icon and sender name
                        const leftContainer = document.createElement('div');
                        leftContainer.style.display = 'flex';
                        leftContainer.style.alignItems = 'center';
                        leftContainer.style.gap = '6px';
                        
                        // Service type icon
                        const serviceIcon = document.createElement('i');
                        serviceIcon.className = 'sms-message-service-icon';
                        serviceIcon.style.fontSize = '11px';
                        
                        const service = message.service || '';
                        if (service.toLowerCase().includes('imessage')) {
                            serviceIcon.className = 'fab fa-apple sms-message-service-icon';
                            serviceIcon.style.color = '#007AFF';
                            serviceIcon.title = 'iMessage';
                        } else if (service.toLowerCase().includes('sms')) {
                        serviceIcon.className = 'fas fa-comment sms-message-service-icon';
                        serviceIcon.style.color = '#34C759';
                        serviceIcon.title = 'SMS';
                    } else if (service === 'WhatsApp') {
                        serviceIcon.className = 'fab fa-whatsapp sms-message-service-icon';
                        serviceIcon.style.color = '#25D366';
                        serviceIcon.title = 'WhatsApp';
                    } else if (service === 'Facebook Messenger') {
                        serviceIcon.className = 'fab fa-facebook-messenger sms-message-service-icon';
                        serviceIcon.style.color = '#0084FF';
                        serviceIcon.title = 'Facebook Messenger';
                    } else if (service === 'Instagram') {
                        serviceIcon.className = 'fab fa-instagram sms-message-service-icon';
                        serviceIcon.style.color = '#E4405F';
                        serviceIcon.title = 'Instagram';
                    } else {
                        // Default icon if service type is unknown
                        serviceIcon.className = 'fas fa-comment sms-message-service-icon';
                        serviceIcon.style.color = '#666';
                        serviceIcon.title = service || 'Message';
                    }
                    
                    const senderSpan = document.createElement('span');
                    senderSpan.className = 'sms-message-sender';
                    senderSpan.textContent = message.sender_name || message.sender_id || (isIncoming ? 'Incoming' : 'Outgoing');
                    
                    leftContainer.appendChild(serviceIcon);
                    leftContainer.appendChild(senderSpan);
                    
                    const dateSpan = document.createElement('span');
                    dateSpan.className = 'sms-message-date';
                    dateSpan.textContent = formatAustralianDate(message.message_date);
                    
                        header.appendChild(leftContainer);
                        messageDiv.appendChild(header);
                    }

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
                        attachmentDiv.style.marginTop = '4px';
                        attachmentDiv.style.borderRadius = '7.5px';
                        attachmentDiv.style.overflow = 'hidden';
                        attachmentDiv.style.cursor = 'pointer';
                        
                        // Check attachment type to display appropriately
                        const contentType = message.attachment_type || '';
                        const isAudio = contentType.startsWith('audio/');
                        const isVideo = contentType.startsWith('video/');
                        const isImage = contentType.startsWith('image/');
                        
                        // Helper function to create fallback display
                        const createFallbackDisplay = (iconClass, iconText) => {
                            attachmentDiv.innerHTML = `<div style="padding: 12px; background-color: rgba(0,0,0,0.05); border-radius: 7.5px; font-size: 13px; color: #667781; display: flex; align-items: center; gap: 8px;"><i class="${iconClass}" style="font-size: 16px;"></i><span>${message.attachment_filename}</span></div>`;
                        };
                        
                        if (isAudio) {
                            // Display audio player inline in the message bubble
                            // Remove overflow hidden for audio to show controls properly
                            attachmentDiv.style.overflow = 'visible';
                            attachmentDiv.style.maxWidth = '300px';
                            
                            const audio = document.createElement('audio');
                            audio.src = `/imessages/${message.id}/attachment`;
                            audio.controls = true;
                            audio.preload = 'metadata'; // Load metadata but not the full audio until play
                            audio.style.width = '100%';
                            audio.style.minWidth = '250px';
                            audio.style.minHeight = '40px';
                            audio.style.height = 'auto';
                            audio.style.display = 'block';
                            audio.style.outline = 'none';
                            audio.style.verticalAlign = 'middle';
                            attachmentDiv.appendChild(audio);
                            // Remove cursor pointer since audio controls handle interaction
                            attachmentDiv.style.cursor = 'default';
                        } else if (isVideo) {
                            // Display video attachment with icon
                            createFallbackDisplay('fas fa-video', 'Video');
                        } else {
                            // For images or unknown types, try to display as image first
                            // This handles cases where attachment_type might not be set
                            const img = document.createElement('img');
                            img.loading = 'lazy'; // Native lazy loading - MUST be set before src
                            img.src = `/imessages/${message.id}/attachment`;
                            img.alt = message.attachment_filename;
                            img.style.maxWidth = '300px';
                            img.style.maxHeight = '300px';
                            img.style.objectFit = 'cover';
                            img.style.display = 'block';
                            img.style.cursor = 'pointer';
                            
                            img.onerror = function() {
                                // If image fails to load, show filename with appropriate icon
                                if (isImage) {
                                    // Known image that failed to load
                                    createFallbackDisplay('fas fa-image', 'Image');
                                } else {
                                    // Unknown file type
                                    createFallbackDisplay('fas fa-file', 'File');
                                }
                            };
                            
                            attachmentDiv.appendChild(img);
                        }
                        
                        // Attach click handler to the attachment div (skip audio since it has inline controls)
                        if (!isAudio) {
                            attachmentDiv.addEventListener('click', () => {
                                showFullAttachment(message.id, message.attachment_filename, message.attachment_type);
                            });
                        }
                        
                        bubble.appendChild(attachmentDiv);
                    }

                    // Timestamp stacked vertically next to bubble - show full date and time
                    const dateTimeContainer = document.createElement('div');
                    dateTimeContainer.style.display = 'flex';
                    dateTimeContainer.style.flexDirection = 'column';
                    dateTimeContainer.style.alignItems = 'flex-start';
                    dateTimeContainer.style.marginLeft = '6px';
                    dateTimeContainer.style.paddingBottom = '2px';
                    dateTimeContainer.style.justifyContent = 'flex-end';
                    
                    // Show full Australian date format: DD/MM/YYYY HH:MM:SS
                    const fullDateStr = formatAustralianDate(message.message_date);
                    const dateTimeParts = fullDateStr.split(' ');
                    
                    // Date part
                    const dateSpan = document.createElement('span');
                    dateSpan.className = 'sms-message-date';
                    dateSpan.style.fontSize = '11px';
                    dateSpan.style.color = '#667781';
                    dateSpan.style.whiteSpace = 'nowrap';
                    dateSpan.style.lineHeight = '1.2';
                    dateSpan.textContent = dateTimeParts[0] || ''; // Date part
                    
                    // Time part
                    const timeSpan = document.createElement('span');
                    timeSpan.className = 'sms-message-time';
                    timeSpan.style.fontSize = '11px';
                    timeSpan.style.color = '#667781';
                    timeSpan.style.whiteSpace = 'nowrap';
                    timeSpan.style.lineHeight = '1.2';
                    timeSpan.textContent = dateTimeParts.length > 1 ? dateTimeParts.slice(1).join(' ') : ''; // Time part(s)
                    
                    dateTimeContainer.appendChild(dateSpan);
                    dateTimeContainer.appendChild(timeSpan);
                    
                    // Wrap bubble and timestamp together
                    const contentWrapper = document.createElement('div');
                    contentWrapper.style.display = 'flex';
                    contentWrapper.style.alignItems = 'flex-end';
                    contentWrapper.style.gap = '6px';
                    contentWrapper.appendChild(bubble);
                    contentWrapper.appendChild(dateTimeContainer);
                    
                    messageDiv.appendChild(contentWrapper);
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
                    // Auto-play the audio
                    modalAudio.play().catch(error => {
                        console.warn('Auto-play prevented by browser:', error);
                        // Audio will still be available for manual play via controls
                    });
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
                    'filter-facebook': 'facebook',
                    'filter-instagram': 'instagram',
                    'filter-mixed': 'mixed'
                };

                // Initialize checkboxes and sync with messageTypeFilters
                Object.keys(filterCheckboxes).forEach(checkboxId => {
                    const checkbox = document.getElementById(checkboxId);
                    if (checkbox) {
                        const filterKey = filterCheckboxes[checkboxId];
                        const label = checkbox.closest('label');
                        
                        // Sync filter state from checkbox's actual checked state
                        // Read the current checkbox state (which may be set by HTML checked attribute)
                        const isChecked = checkbox.checked;
                        messageTypeFilters[filterKey] = isChecked;
                        
                        // Update label styling based on checked state
                        if (label) {
                            const icon = label.querySelector('i');
                            const textSpan = label.querySelector('span');
                            
                            if (isChecked) {
                                label.style.backgroundColor = '#d1e7dd';
                                label.style.borderColor = '#0f5132';
                                if (icon) icon.style.color = '#0f5132';
                                if (textSpan) {
                                    textSpan.style.color = '#0f5132';
                                    textSpan.style.fontWeight = '600';
                                }
                            } else {
                                label.style.backgroundColor = '#f0f2f5';
                                label.style.borderColor = '#f0f2f5';
                                // Reset icon colors to their original
                                if (icon) {
                                    const iconClass = icon.className;
                                    if (iconClass.includes('fa-apple')) icon.style.color = '#007AFF';
                                    else if (iconClass.includes('fa-comment') && !iconClass.includes('fa-comments')) icon.style.color = '#34C759';
                                    else if (iconClass.includes('fa-whatsapp')) icon.style.color = '#25D366';
                                    else if (iconClass.includes('fa-facebook-messenger')) icon.style.color = '#0084FF';
                                    else if (iconClass.includes('fa-instagram')) icon.style.color = '#E4405F';
                                    else if (iconClass.includes('fa-comments')) icon.style.color = '#FF9500';
                                    else icon.style.color = '#54656f';
                                }
                                if (textSpan) {
                                    textSpan.style.color = '#54656f';
                                    textSpan.style.fontWeight = 'normal';
                                }
                            }
                        }
                        
                        checkbox.addEventListener('change', (e) => {
                            const newValue = Boolean(e.target.checked);
                            messageTypeFilters[filterKey] = newValue;
                            
                            // Update label styling
                            if (label) {
                                const icon = label.querySelector('i');
                                const textSpan = label.querySelector('span');
                                
                                if (newValue) {
                                    label.style.backgroundColor = '#d1e7dd';
                                    label.style.borderColor = '#0f5132';
                                    if (icon) icon.style.color = '#0f5132';
                                    if (textSpan) {
                                        textSpan.style.color = '#0f5132';
                                        textSpan.style.fontWeight = '600';
                                    }
                                } else {
                                    label.style.backgroundColor = '#f0f2f5';
                                    label.style.borderColor = '#f0f2f5';
                                    // Reset icon colors to their original
                                    if (icon) {
                                        const iconClass = icon.className;
                                        if (iconClass.includes('fa-apple')) icon.style.color = '#007AFF';
                                        else if (iconClass.includes('fa-comment') && !iconClass.includes('fa-comments')) icon.style.color = '#34C759';
                                        else if (iconClass.includes('fa-whatsapp')) icon.style.color = '#25D366';
                                        else if (iconClass.includes('fa-facebook-messenger')) icon.style.color = '#0084FF';
                                        else if (iconClass.includes('fa-instagram')) icon.style.color = '#E4405F';
                                        else if (iconClass.includes('fa-comments')) icon.style.color = '#FF9500';
                                        else icon.style.color = '#54656f';
                                    }
                                    if (textSpan) {
                                        textSpan.style.color = '#54656f';
                                        textSpan.style.fontWeight = 'normal';
                                    }
                                }
                            }
                            
                            renderChatSessions();
                        });
                    } else {
                        console.warn(`Checkbox not found: ${checkboxId}`);
                    }
                });
                
                // After initializing all checkboxes, ensure filter state is synced
                // and trigger a render if sessions are already loaded
                if (chatSessions.length > 0) {
                    renderChatSessions();
                }

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
                        const selectedOption = document.querySelector('input[name="sms-ask-ai-option"]:checked')?.value;
                        const otherText = askAIOtherInput?.value || '';

                        // Close the Ask AI modal
                        if (askAIModal) {
                            askAIModal.style.display = 'none';
                        }

                        // Handle "Summarise the Conversation" option
                        if (selectedOption === 'summarise') {
                            if (!currentSession) {
                                alert('No conversation selected');
                                return;
                            }

                            try {
                                // Open the conversation summary modal
                                // currentSession is already the chat session name (string)
                                Modals.ConversationSummary.open(currentSession);
                            } catch (error) {
                                console.error('Error opening conversation summary:', error);
                                alert('Failed to start conversation summarization. Please try again.');
                            }
                        } else if (selectedOption === 'imaginary') {
                            // TODO: Implement imaginary conversation functionality
                            alert('Imaginary conversation feature coming soon!');
                        } else if (selectedOption === 'other') {
                            // TODO: Implement other AI functionality
                            alert('Other AI features coming soon!');
                        }
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

            async function open() {
                const modal = document.getElementById('sms-messages-modal');
                if (modal) {
                    modal.style.display = 'flex';
                    // Re-initialize filters from checkboxes when modal opens
                    // This ensures filter state matches checkbox state
                    const filterCheckboxes = {
                        'filter-imessage': 'imessage',
                        'filter-sms': 'sms',
                        'filter-whatsapp': 'whatsapp',
                        'filter-facebook': 'facebook',
                        'filter-instagram': 'instagram',
                        'filter-mixed': 'mixed'
                    };
                    
                    Object.keys(filterCheckboxes).forEach(checkboxId => {
                        const checkbox = document.getElementById(checkboxId);
                        if (checkbox) {
                            const filterKey = filterCheckboxes[checkboxId];
                            const label = checkbox.closest('label');
                            const isChecked = Boolean(checkbox.checked);
                            messageTypeFilters[filterKey] = isChecked;
                            
                            // Update label styling
                            if (label) {
                                const icon = label.querySelector('i');
                                const textSpan = label.querySelector('span');
                                
                                if (isChecked) {
                                    label.style.backgroundColor = '#d1e7dd';
                                    label.style.borderColor = '#0f5132';
                                    if (icon) icon.style.color = '#0f5132';
                                    if (textSpan) {
                                        textSpan.style.color = '#0f5132';
                                        textSpan.style.fontWeight = '600';
                                    }
                                } else {
                                    label.style.backgroundColor = '#f0f2f5';
                                    label.style.borderColor = '#f0f2f5';
                                    // Reset icon colors to their original
                                    if (icon) {
                                        const iconClass = icon.className;
                                        if (iconClass.includes('fa-apple')) icon.style.color = '#007AFF';
                                        else if (iconClass.includes('fa-comment') && !iconClass.includes('fa-comments')) icon.style.color = '#34C759';
                                        else if (iconClass.includes('fa-whatsapp')) icon.style.color = '#25D366';
                                        else if (iconClass.includes('fa-facebook-messenger')) icon.style.color = '#0084FF';
                                        else if (iconClass.includes('fa-instagram')) icon.style.color = '#E4405F';
                                        else if (iconClass.includes('fa-comments')) icon.style.color = '#FF9500';
                                        else icon.style.color = '#54656f';
                                    }
                                    if (textSpan) {
                                        textSpan.style.color = '#54656f';
                                        textSpan.style.fontWeight = 'normal';
                                    }
                                }
                            }
                        }
                    });
                    
                    await loadChatSessions()
                }
            }
            async function openAndSelectConversation(messageID){
                // Open the modal first
                open();
                
                try {
                    // Retrieve the message metadata by messageID
                    const messageResponse = await fetch(`/imessages/${messageID}/metadata`);
                    if (!messageResponse.ok) {
                        throw new Error(`Failed to fetch message metadata: ${messageResponse.status}`);
                    }
                    
                    const messageMetadata = await messageResponse.json();
                    const chatSession = messageMetadata.chat_session;
                    
                    if (!chatSession) {
                        console.error('Message metadata does not contain chat_session');
                        alert('Unable to open conversation: Message has no chat session');
                        return;
                    }
                    
                    // Load chat sessions if not already loaded
                    if (chatSessions.length === 0) {
                        await loadChatSessions();
                    }
                    
                    // Wait a bit for the DOM to update after loading sessions
                    await new Promise(resolve => setTimeout(resolve, 100));
                    
                    // Find the conversation by chat_session name
                    const conversation = chatSessions.find(s => s.chat_session === chatSession);
                    
                    if (conversation) {
                        // Select the conversation (this loads and displays messages)
                        await selectChatSession(chatSession);
                        
                        // Wait for messages to be rendered in the DOM
                        await new Promise(resolve => setTimeout(resolve, 200));
                        
                        // Scroll to the specific message
                        const message = document.getElementById('message-'+messageID);
                        if (message) {
                            message.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        } else {
                            console.warn(`Message with ID ${messageID} not found in DOM`);
                        }
                    } else {
                        console.warn(`Conversation with chat_session "${chatSession}" not found`);
                        // Still render sessions even if the specific one isn't found
                        renderChatSessions();
                        alert(`Conversation "${chatSession}" not found in the list`);
                    }
                } catch (error) {
                    console.error('Error opening conversation:', error);
                    alert('Failed to open conversation. Please try again.');
                    // Still render sessions on error
                    if (chatSessions.length === 0) {
                        await loadChatSessions();
                    } else {
                        renderChatSessions();
                    }
                }
            }
            

            function close() {
                const modal = document.getElementById('sms-messages-modal');
                if (modal) {
                    modal.style.display = 'none';
                }
            }

            return { init, open, close,openAndSelectConversation };
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
                    if (file_id.startsWith('/getImage') || file_id.startsWith('/images/')) {
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
                
                Modals._closeModal(DOM.singleImageModal);
            }

            return { init, showSingleImageModal};
        })(),

        ReferenceDocuments: (() => {
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
        })(),

        Contacts: (() => {
            async function loadContacts() {
                if (!DOM.contactsLoading || !DOM.contactsTableContainer || !DOM.contactsTableBody) return;
                DOM.contactsLoading.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading contacts...';
                DOM.contactsLoading.style.display = 'block';
                DOM.contactsTableContainer.style.display = 'none';
                try {
                    const response = await fetch('/contacts?limit=500');
                    if (!response.ok) throw new Error('Failed to load contacts');
                    const data = await response.json();
                    const contacts = data.contacts || [];
                    DOM.contactsTableBody.innerHTML = '';
                    contacts.forEach(c => {
                        const row = document.createElement('tr');
                        row.style.borderBottom = '1px solid #eee';
                        row.innerHTML = `
                            <td style="padding: 8px;">${escapeHtml(c.name || '')}</td>
                            <td style="padding: 8px;">${escapeHtml(c.email || '-')}</td>
                            <td style="padding: 8px;">${escapeHtml(c.smsid || '-')}</td>
                            <td style="padding: 8px;">${escapeHtml(c.whatsappid || '-')}</td>
                            <td style="padding: 8px;">${escapeHtml(c.imessageid || '-')}</td>
                            <td style="padding: 8px;">${escapeHtml(c.instagramid || '-')}</td>
                            <td style="padding: 8px;">${escapeHtml(c.facebookid || '-')}</td>
                        `;
                        DOM.contactsTableBody.appendChild(row);
                    });
                    DOM.contactsLoading.style.display = 'none';
                    DOM.contactsTableContainer.style.display = 'block';
                } catch (err) {
                    console.error('Error loading contacts:', err);
                    DOM.contactsLoading.innerHTML = `<span style="color: #c00;">Error: ${err.message}</span>`;
                    DOM.contactsLoading.style.display = 'block';
                    DOM.contactsTableContainer.style.display = 'none';
                }
            }
            function escapeHtml(text) {
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }
            function open() {
                Modals._openModal(DOM.contactsModal);
                loadContacts();
            }
            function close() {
                Modals._closeModal(DOM.contactsModal);
            }
            async function extractContacts() {
                if (!DOM.extractContactsBtn) return;
                const btn = DOM.extractContactsBtn;
                const origHtml = btn.innerHTML;
                btn.disabled = true;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Extracting...';
                try {
                    const response = await fetch('/contacts/extract', { method: 'POST' });
                    if (!response.ok) {
                        const err = await response.json().catch(() => ({}));
                        throw new Error(err.detail || `HTTP ${response.status}`);
                    }
                    const data = await response.json();
                    await loadContacts();
                    if (data.created || data.updated) {
                        alert(`Extracted: ${data.created || 0} created, ${data.updated || 0} updated`);
                    }
                } catch (err) {
                    console.error('Error extracting contacts:', err);
                    alert(`Error: ${err.message}`);
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = origHtml;
                }
            }
            function init() {
                if (DOM.closeContactsModalBtn) DOM.closeContactsModalBtn.addEventListener('click', close);
                if (DOM.contactsModal) DOM.contactsModal.addEventListener('click', (e) => { if (e.target === DOM.contactsModal) close(); });
                if (DOM.extractContactsBtn) DOM.extractContactsBtn.addEventListener('click', extractContacts);
            }
            return { init, open, close };
        })(),

        Relationships: (() => {
            let cy = null;
            let hideTimeout = null;

            function getTypeFilterParams() {
                const types = ['friend', 'family', 'colleague', 'acquaintance', 'business', 'social', 'promotional', 'unknown'];
                const selected = types.filter(t => {
                    const cb = document.getElementById('rel-type-' + t);
                    return cb && cb.checked;
                });
                return selected.length > 0 ? selected.join(',') : null;
            }

            function getSourceFilterParams() {
                const sources = ['email', 'facebook', 'whatsapp', 'sms-imessage', 'instagram'];
                const selected = sources.filter(s => {
                    const cb = document.getElementById('rel-source-' + s);
                    return cb && cb.checked;
                });
                return selected.length > 0 ? selected.join(',') : null;
            }

            async function fetchData() {
                const typeParam = getTypeFilterParams();
                const sourceParam = getSourceFilterParams();
                const url = new URL('/relationships/sample', window.location.origin);
                if (typeParam) url.searchParams.set('types', typeParam);
                if (sourceParam) url.searchParams.set('sources', sourceParam);
                const response = await fetch(url.toString());
                if (!response.ok) throw new Error('Failed to load relationship data');
                return response.json();
            }

            function updateGraph() {
                if (!cy) return;
                const slider = document.getElementById('rel-filter-slider');
                const sizeSlider = document.getElementById('rel-size-slider');
                if (!slider || !sizeSlider ) return;
                const threshold = parseInt(slider.value);
                const baseSize = parseFloat(sizeSlider.value);
                const hub = cy.getElementById('0');

                cy.elements().removeClass('hidden');
                cy.edges().forEach(e => { if (e.data('strength') < threshold) e.addClass('hidden'); });


                cy.nodes().forEach(n => { if (n.connectedEdges(':visible').length === 0) n.addClass('hidden'); });
                

                const visible = cy.nodes(':visible');
                if (visible.length > 0) {
                    const degrees = visible.map(n => n.connectedEdges(':visible').length);
                    const min = Math.min(...degrees), max = Math.max(...degrees);
                    const maxSize = baseSize * 4;
                    visible.forEach(n => {
                        const deg = n.connectedEdges(':visible').length;
                        let s = baseSize;
                        if(max !== min) s = baseSize + (deg - min) * (maxSize - baseSize) / (max - min);
                        n.style({'width': s, 'height': s});
                    });
                }
            }

            function reLayout() {
                if (!cy) return;
                updateGraph();
                const hub = cy.getElementById('Dave Burton');
                hub.unlock();
                hub.position({ x: cy.width() / 2, y: cy.height() / 2 });
                hub.lock();
                const layout = cy.layout({ name: 'cose', animate: true, fit: false, nodeRepulsion: () => 800000, gravity: 2, eles: cy.elements(':visible') });
                layout.one('layoutstop', () => { cy.animate({ center: { eles: hub }, zoom: 0.7, duration: 800 }); });
                layout.run();
            }

            function resetView() {
                if (cy) cy.animate({ fit: { eles: cy.elements(':visible'), padding: 50 }, duration: 500 });
            }

            function setupEvents() {
                const balloon = document.getElementById('rel-balloon');
                const searchInput = document.getElementById('rel-search-input');
                const filterSlider = document.getElementById('rel-filter-slider');
                const sizeSlider = document.getElementById('rel-size-slider');
                const strVal = document.getElementById('rel-str-val');
                const sizeVal = document.getElementById('rel-size-val');
                if (!balloon || !cy) return;

                if (searchInput) {
                    searchInput.addEventListener('input', (e) => {
                        const text = e.target.value.toLowerCase();
                        if (!text) return;
                        const found = cy.nodes().filter(n => n.data('name').toLowerCase().includes(text));
                        if (found.length > 0) { cy.animate({ center: { eles: found[0] }, zoom: 1.2, duration: 400 }); found[0].select(); }
                    });
                }

                cy.on('mouseover', 'node', function(e) {
                    const node = e.target;
                    const neighborhood = node.closedNeighborhood();
                    cy.elements().addClass('faded');
                    neighborhood.removeClass('faded').addClass('highlight');
                });

                cy.on('mouseout', 'node', function() {
                    cy.elements().removeClass('faded highlight');
                });

                function positionBalloon(renderedPos) {
                    const container = document.querySelector('.rel-cy-container');
                    if (!container) return;
                    const rect = container.getBoundingClientRect();
                    balloon.style.top = (renderedPos.y - rect.top - 40) + 'px';
                    balloon.style.left = (renderedPos.x - rect.left + 10) + 'px';
                }

                cy.on('tap', 'edge', function(e) {
                    const edge = e.target;
                    clearTimeout(hideTimeout);
                    cy.edges().unselect();
                    edge.select();
                    balloon.innerHTML = `<strong>Strength: ${edge.data('strength')}/10</strong>`;
                    balloon.style.display = 'block';
                    positionBalloon(e.renderedPosition);
                    hideTimeout = setTimeout(() => { balloon.style.display = 'none'; edge.unselect(); }, 3000);
                });

                const CONTACT_TYPES = ['friend', 'family', 'colleague', 'acquaintance', 'business', 'social', 'promotional', 'spam', 'important', 'unknown'];
                cy.on('tap', 'node', function(e) {
                    const node = e.target;
                    balloon.style.display = 'none';
                    const detailsPanel = document.getElementById('rel-node-details');
                    if (!detailsPanel) return;
                    const nodeId = node.id();
                    const nodeName = node.data('name');
                    const currentType = node.data('contact_type') || 'unknown';
                    const edges = node.connectedEdges(':visible');
                    const connections = edges.map(edge => {
                        const other = edge.source().id() === nodeId ? edge.target() : edge.source();
                        return { name: other.data('name'), strength: edge.data('strength') };
                    });
                    let html = `<strong>${nodeName}</strong><br>Connections: ${connections.length}`;
                    if (connections.length > 0) {
                        html += '<ul style="margin: 0.5em 0 0 1.2em; padding: 0;">';
                        connections.forEach(c => {
                            html += `<li>${c.name} <span style="color:#666">(strength ${c.strength}/10)</span></li>`;
                        });
                        html += '</ul>';
                    }
                    if (nodeId !== '0') {
                        html += '<label style="display:block; margin-top: 0.75em; font-weight: 600;">Contact Type:</label>';
                        html += '<select id="rel-contact-type-select" style="margin-top: 0.25em; width: 100%; padding: 4px 8px; font-size: 0.9em;">';
                        CONTACT_TYPES.forEach(t => {
                            const label = t.charAt(0).toUpperCase() + t.slice(1);
                            html += `<option value="${t}" ${t === currentType ? 'selected' : ''}>${label}</option>`;
                        });
                        html += '</select>';
                    }
                    detailsPanel.innerHTML = html;
                    if (nodeId !== '0') {
                        const select = document.getElementById('rel-contact-type-select');
                        if (select) {
                            select.addEventListener('change', async function() {
                                const newType = this.value;
                                try {
                                    const res = await fetch('/contacts/update-classification', {
                                        method: 'PATCH',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify({ name: nodeName, classification: newType })
                                    });
                                    if (!res.ok) {
                                        const err = await res.json().catch(() => ({}));
                                        const msg = Array.isArray(err.detail) ? err.detail.map(d => d.msg || JSON.stringify(d)).join('; ') : (err.detail || res.statusText);
                                        throw new Error(msg);
                                    }
                                    node.data('contact_type', newType);
                                    if (typeof UI !== 'undefined' && UI.displayError) UI.displayError(null);
                                } catch (err) {
                                    if (typeof UI !== 'undefined' && UI.displayError) {
                                        UI.displayError('Failed to save: ' + (err.message || 'Unknown error'));
                                    } else {
                                        alert('Failed to save: ' + (err.message || 'Unknown error'));
                                    }
                                    select.value = currentType;
                                }
                            });
                        }
                    }
                });

                cy.on('tap', function(e) {
                    if (e.target === cy) {
                        balloon.style.display = 'none';
                        cy.edges().unselect();
                        const detailsPanel = document.getElementById('rel-node-details');
                        if (detailsPanel) {
                            detailsPanel.innerHTML = '<em style="color: #666;">Click a person to view details</em>';
                        }
                    }
                });

                if (filterSlider && strVal) filterSlider.oninput = function() { strVal.innerText = this.value; updateGraph(); };
                if (sizeSlider && sizeVal) sizeSlider.oninput = function() { sizeVal.innerText = this.value; updateGraph(); };

            }

            async function initGraph() {
                const container = document.getElementById('rel-cy');
                if (!container || typeof cytoscape === 'undefined') return;
                let data;
                try {
                    data = await fetchData();
                } catch (err) {
                    console.error('Relationships fetch failed:', err);
                    if (typeof UI !== 'undefined' && UI.displayError) UI.displayError('Could not load relationship data: ' + (err.message || 'Unknown error'));
                    else alert('Could not load relationship data. Please try again.');
                    return;
                }
                const elements = [...data.nodes.map(n => ({data: n})), ...data.links.map(l => ({data: l}))];

                cy = cytoscape({
                    container: container,
                    elements: elements,
                    style: [
                        { selector: 'node', style: { 'background-color': '#4285f4', 'label': 'data(name)', 'font-size': '10px', 'text-valign': 'bottom', 'text-margin-y': 4 } },
                        { selector: 'node[id="0"]', style: { 'background-color': '#1a73e8', 'border-width': 3, 'border-color': '#000', 'z-index': 1000 } },
                        { selector: 'edge', style: { 'width': 'data(strength)', 'line-color': '#e0e0e0', 'curve-style': 'bezier', 'opacity': 0.6 } },
                        { selector: 'edge[source="0"], edge[target="0"]', style: { 'line-color': '#bbdefb' } },
                        { selector: '.hidden', style: { 'display': 'none' } },
                        { selector: 'edge:selected', style: { 'line-color': '#ff5722', 'opacity': 1, 'z-index': 999 } },
                        { selector: '.faded', style: { 'opacity': 0.08, 'text-opacity': 0 } },
                        { selector: '.highlight', style: { 'opacity': 1, 'text-opacity': 1, 'z-index': 9999 } }
                    ]
                });

                setupEvents();
                reLayout();
                
            }

            function open() {
                Modals._openModal(DOM.relationshipsModal);
                initGraph();
            }

            function close() {
                if (cy) {
                    try { cy.destroy(); } catch (e) { console.debug('Error destroying cytoscape:', e); }
                    cy = null;
                }
                clearTimeout(hideTimeout);
                Modals._closeModal(DOM.relationshipsModal);
            }

            function init() {
                if (DOM.closeRelationshipsModalBtn) DOM.closeRelationshipsModalBtn.addEventListener('click', close);
                if (DOM.relationshipsModal) DOM.relationshipsModal.addEventListener('click', (e) => { if (e.target === DOM.relationshipsModal) close(); });
                const pinBtn = document.getElementById('rel-pin-center-btn');
                const fitBtn = document.getElementById('rel-fit-all-btn');
                const applyBtn = document.getElementById('rel-apply-filters-btn');
                if (pinBtn) pinBtn.addEventListener('click', reLayout);
                if (fitBtn) fitBtn.addEventListener('click', resetView);
                if (applyBtn) applyBtn.addEventListener('click', () => { initGraph(); });
            }

            return { init, open, close };
        })(),

        ReferenceDocumentsNotification: (() => {
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
                debugger;
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
        })(),

        ConversationManager: (() => {
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
        })(),

        SubjectConfiguration: (() => {
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

            function updatePageReferences(subjectName, newGender) {
                if (!subjectName) return;

                // Update page title
                document.title = `Let's Talk About ${subjectName}`;

                // Update header
                const header = document.querySelector('.header-container h2');
                if (header) {
                    header.textContent = `Let's Talk About ${subjectName}`;
                }

                if (CONSTANTS.VOICE_DESCRIPTIONS["dave"]) {
                    CONSTANTS.VOICE_DESCRIPTIONS["dave"] = CONSTANTS.VOICE_DESCRIPTIONS["dave"].replace('{SUBJECT_NAME}', subjectName);
                }

                const exploreDaveWorldHeading = document.getElementById('explore-dave-world-heading');
                if (exploreDaveWorldHeading) {
                    exploreDaveWorldHeading.textContent = `Explore ${subjectName}'s World`;
                }

                debugger;

                const daveImage = document.querySelector('.voice-icon[alt="dave"]');
                const admireImage = document.querySelector('.voice-icon[alt="secret-admirer"]');
 
                if (newGender === 'Female') {
                    // set the image source of the image with class voice-icon and  alt="dave" to /static/images/secret-admirer_sm.png

                    CONSTANTS.VOICE_IMAGES["dave"] = "secret-admirer.png";
                    CONSTANTS.VOICE_IMAGES["dave_sm"] = "secret-admirer_sm.png";
                    CONSTANTS.VOICE_IMAGES["secret_admirer"] = "dave.png";
                    CONSTANTS.VOICE_IMAGES["secret_admirer_sm"] = "dave_sm.png";



                    if (daveImage) {
                        daveImage.src = '/static/images/secret-admirer_sm.png';
                    }
                    
                    if (admireImage) {
                        admireImage.src = '/static/images/dave_sm.png';
                    }

                } else {

                    
                    CONSTANTS.VOICE_IMAGES["dave"] = "dave.png";
                    CONSTANTS.VOICE_IMAGES["dave_sm"] = "dave_sm.png";
                    CONSTANTS.VOICE_IMAGES["secret_admirer"] = "secret-admirer.png";
                    CONSTANTS.VOICE_IMAGES["secret_admirer_sm"] = "secret-admirer_sm.png";

                    if (admireImage) {
                        admireImage.src = '/static/images/secret-admirer_sm.png';
                    }
                    
                    if (daveImage) {
                        daveImage.src = '/static/images/dave_sm.png';
                    }
                }
                console.log("Images Updated");

                // Update info box references
                const infoBox = document.getElementById('info-box');
                if (infoBox) {
                    let text = infoBox.innerHTML;
                    // Replace common references
                    text = text
                        .replace(/Dave/g, subjectName)
                        .replace(/Dave's/g, `${subjectName}'s`)
                        .replace(/David Burton/g, subjectName);
                    // Apply pronoun replacements if gender changed
                    //text = applyPronounReplacements(text);
                    infoBox.innerHTML = text;
                }

                // Update voice descriptions dynamically
                const voiceIcons = document.querySelectorAll('.voice-icon-wrapper');
                voiceIcons.forEach(icon => {
                    const description = icon.getAttribute('data-description');
                    if (description) {
                        let updatedDescription = description;
                        if (description.includes('Dave')) {
                            updatedDescription = updatedDescription
                                .replace(/Dave/g, subjectName)
                                .replace(/Dave's/g, `${subjectName}'s`);
                        }
                        // Apply pronoun replacements if gender changed
                        //updatedDescription = applyPronounReplacements(updatedDescription);
                        icon.setAttribute('data-description', updatedDescription);
                        const title = icon.querySelector('.voice-icon-title');
                        if (title) {
                            title.textContent = updatedDescription;
                        }
                    }
                });

                // Update voice select dropdown options
                const voiceSelect = DOM.voiceSelect || document.getElementById('voice-select');
                if (voiceSelect) {
                    const options = voiceSelect.querySelectorAll('option');
                    options.forEach(option => {
                        let text = option.textContent;
                        if (text.includes('Dave')) {
                            text = text
                                .replace(/Dave/g, subjectName)
                                .replace(/Dave's/g, `${subjectName}'s`);
                        }
                        // Apply pronoun replacements if gender changed
                        //text = applyPronounReplacements(text);
                        option.textContent = text;
                    });
                }

                // Update current gender state after processing
                if (newGender) {
                    currentGender = newGender;
                }
            }

            async function checkAndShow() {
                if (configurationLoaded && currentSubjectName) {
                    updatePageReferences(currentSubjectName, currentGender);
                    return;
                }

                const config = await loadConfiguration();
                if (!config) {
                    // No configuration exists, show modal
                    showModal();
                } else {
                    // Configuration exists, update references
                    updatePageReferences(config.subject_name, config.gender || 'Male');
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
                    updatePageReferences(subjectName, gender);
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
                updatePageReferences,
                showModal,
                close: closeModal
            };
        })(),

        initAll: () => {
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
        },

        closeAll: () => {
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
        }
    };


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

            AppState.isInterviewerMode = !AppState.isInterviewerMode;
            
            if (AppState.isInterviewerMode) {

                
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

                DOM.interviewerModeBtn.addEventListener('click', async () => {
                    await toggleInterviewerMode();
                });
                
                // Add a simple test click handler

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

            addInterviewerMessage('system', 'Interview finished. You can now write the final biography or exit interview mode.', false);
            // Update interview state to 'finished' and enable appropriate buttons
            AppState.interviewState = 'finished';
            updateInterviewControlButtons();
            // Disable input controls
            setInterviewerControlsEnabled(false);
        }

        async function handleWriteFinalBio() {
 
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
        // [CONSTANTS.FUNCTION_NAMES.ThirdFunction]: () => Modals.FBAlbums.open(),    // showFBAlbumsOptions
        // [CONSTANTS.FUNCTION_NAMES.FourthFunction]: () => Modals.Locations.open(), // showGeoMetadataOptions
        // [CONSTANTS.FUNCTION_NAMES.FifthFunction]: () => SSE.browserFunctions.showLocationInfo(), // showTileAlbumOptions
        // [CONSTANTS.FUNCTION_NAMES.SixthFunction]: () => Modals.ImageGallery.open(),
        // [CONSTANTS.FUNCTION_NAMES.SeventhFunction]: () => SSE.browserFunctions.testEmail(), // showImageGalleryOptions
        // [CONSTANTS.FUNCTION_NAMES.EighthFunction]: () => Modals.EmailGallery.open() // showEmailGalleryOptions

    };
    window.customObject = AppActions; // Expose for Suggestions.json if it relies on global `customObject`


    // --- Main Application Logic & Initialization ---
    const App = (() => {
        async function processFormSubmit(userPrompt, category = null, title = null, supplementary_prompt = null) {
            if (!userPrompt && !category && !title) return;

            // Check and show reference documents notification before proceeding
            await Modals.ReferenceDocumentsNotification.checkAndShow(async () => {
                // This callback is called when user proceeds
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
                        thumbnails: 'import-last-run-thumbnails'
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
                thumbnails: '/images/process-thumbnails/cancel'
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
                thumbnails: { needsInput: false, title: 'Image Processing', run: async () => { const r = await fetch('/images/process-thumbnails', { method: 'POST' }); return r; }, stream: '/images/process-thumbnails/stream' }
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

            async function checkInitialImportStatus() {
                const types = ['email_processing','imessage','whatsapp','facebook','instagram','facebook_albums','facebook_places','filesystem','thumbnails'];
                const statusEndpoints = { email_processing: '/emails/process/status', imessage: '/imessages/import/status', whatsapp: '/whatsapp/import/status', facebook: '/facebook/import/status', instagram: '/instagram/import/status', facebook_albums: '/facebook/albums/import/status', facebook_places: '/facebook/import-places/status', filesystem: '/images/import/status', thumbnails: '/images/process-thumbnails/status' };
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

            if (DOM.emailEditorSidebarBtn) {
                DOM.emailEditorSidebarBtn.addEventListener('click', () => {
                    Modals.EmailEditor.open();
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
            //SSE.init();
            //InterviewerMode.init(); // Initialize interviewer mode
            initEventListeners(); // Attach main app event listeners

            // Initial info box visibility
            if (DOM.chatBox.querySelectorAll('.message').length === 0 && DOM.infoBox) {
                DOM.infoBox.classList.remove('hidden');
                if (!DOM.chatBox.contains(DOM.infoBox)) DOM.chatBox.appendChild(DOM.infoBox);
            } else if (DOM.infoBox) {
                DOM.infoBox.classList.add('hidden');
            }
             window.onbeforeunload = () => { SSE.close(); };
        }
        return { init, processFormSubmit };
    })();

    App.init();


});



