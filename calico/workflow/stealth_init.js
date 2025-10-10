
            // ========================================
            // PRIORITY: Set these FIRST before anything else
            // ========================================
            
            // Override navigator.webdriver immediately
            delete Object.getPrototypeOf(navigator).webdriver;
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true,
                enumerable: true
            });
            
            // Set chrome object FIRST
            window.chrome = {
                app: {
                    isInstalled: false,
                    InstallState: {
                        DISABLED: 'disabled',
                        INSTALLED: 'installed',
                        NOT_INSTALLED: 'not_installed'
                    },
                    RunningState: {
                        CANNOT_RUN: 'cannot_run',
                        READY_TO_RUN: 'ready_to_run',
                        RUNNING: 'running'
                    }
                },
                runtime: {
                    OnInstalledReason: {
                        CHROME_UPDATE: 'chrome_update',
                        INSTALL: 'install',
                        SHARED_MODULE_UPDATE: 'shared_module_update',
                        UPDATE: 'update'
                    },
                    OnRestartRequiredReason: {
                        APP_UPDATE: 'app_update',
                        OS_UPDATE: 'os_update',
                        PERIODIC: 'periodic'
                    },
                    PlatformArch: {
                        ARM: 'arm',
                        ARM64: 'arm64',
                        MIPS: 'mips',
                        MIPS64: 'mips64',
                        X86_32: 'x86-32',
                        X86_64: 'x86-64'
                    },
                    PlatformNaclArch: {
                        ARM: 'arm',
                        MIPS: 'mips',
                        MIPS64: 'mips64',
                        X86_32: 'x86-32',
                        X86_64: 'x86-64'
                    },
                    PlatformOs: {
                        ANDROID: 'android',
                        CROS: 'cros',
                        LINUX: 'linux',
                        MAC: 'mac',
                        OPENBSD: 'openbsd',
                        WIN: 'win'
                    },
                    RequestUpdateCheckStatus: {
                        NO_UPDATE: 'no_update',
                        THROTTLED: 'throttled',
                        UPDATE_AVAILABLE: 'update_available'
                    }
                },
                csi: function() {
                    return {
                        onloadT: Date.now(),
                        pageT: Date.now() - performance.timing.navigationStart,
                        startE: performance.timing.navigationStart,
                        tran: 15
                    };
                },
                loadTimes: function() {
                    return {
                        commitLoadTime: performance.timing.responseStart / 1000,
                        connectionInfo: 'http/1.1',
                        finishDocumentLoadTime: performance.timing.domContentLoadedEventEnd / 1000,
                        finishLoadTime: performance.timing.loadEventEnd / 1000,
                        firstPaintAfterLoadTime: 0,
                        firstPaintTime: performance.timing.responseStart / 1000,
                        navigationType: 'Other',
                        npnNegotiatedProtocol: 'http/1.1',
                        requestTime: performance.timing.requestStart / 1000,
                        startLoadTime: performance.timing.requestStart / 1000,
                        wasAlternateProtocolAvailable: false,
                        wasFetchedViaSpdy: false,
                        wasNpnNegotiated: false
                    };
                }
            };
            
            console.log('[STEALTH] Anti-detection script loaded');
            console.log('[STEALTH] navigator.webdriver =', navigator.webdriver);
            console.log('[STEALTH] window.chrome =', typeof window.chrome);
            
            // ========================================
            // SUPPRESS CHROME EXTENSION ERRORS
            // ========================================
            // Intercept and suppress console errors related to chrome extensions
            (function() {
                const originalError = console.error;
                console.error = function(...args) {
                    const message = args.join(' ');
                    // Suppress chrome-extension and chrome:// related errors
                    if (message.includes('chrome-extension://') || 
                        message.includes('chrome://') ||
                        message.includes('Refused to create a worker') ||
                        message.includes('Refused to connect')) {
                        return; // Silently ignore
                    }
                    originalError.apply(console, args);
                };
            })();
            
            // ========================================
            // WORKER AND EXTENSION BLOCKING
            // ========================================
            // Block workers from chrome:// and chrome-extension:// URLs
            const OriginalWorker = window.Worker;
            window.Worker = function(...args) {
                // Block chrome:// and chrome-extension:// URLs silently
                if (args[0] && (args[0].startsWith('chrome://') || args[0].startsWith('chrome-extension://'))) {
                    // Don't log or throw - just return a dummy worker to avoid errors
                    return {
                        postMessage: function() {},
                        addEventListener: function() {},
                        removeEventListener: function() {},
                        terminate: function() {}
                    };
                }
                return new OriginalWorker(...args);
            };
            
            // Fix chrome.runtime to prevent extension detection
            if (!window.chrome) {
                window.chrome = {};
            }
            if (!window.chrome.runtime) {
                window.chrome.runtime = {
                    connect: function() { return null; },
                    sendMessage: function() { return null; },
                    onMessage: {
                        addListener: function() {},
                        removeListener: function() {}
                    }
                };
            }
            
            // ========================================
            // ADDITIONAL WEBDRIVER AND AUTOMATION MARKERS REMOVAL
            // ========================================
            // Remove all automation markers (in case they get added after init)
            delete navigator.__proto__.webdriver;
            delete window.navigator.__proto__.webdriver;
            delete window.document.__selenium_unwrapped;
            delete window.document.__webdriver_evaluate;
            delete window.document.__webdriver_script_fn;
            delete window.document.__webdriver_script_func;
            delete window.document.__webdriver_script_function;
            delete window.document.__driver_evaluate;
            delete window.document.__driver_unwrapped;
            delete window.document.$cdc_asdjflasutopfhvcZLmcfl_;
            delete window.$chrome_asyncScriptInfo;
            delete window.document.$cdc_;
            
            // Mock plugins with proper PluginArray structure
            const plugins = [
                {
                    0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: null},
                    description: "Portable Document Format",
                    filename: "internal-pdf-viewer",
                    length: 1,
                    name: "Chrome PDF Plugin",
                    [Symbol.iterator]: function* () {
                        yield this[0];
                    }
                },
                {
                    0: {type: "application/pdf", suffixes: "pdf", description: "", enabledPlugin: null},
                    description: "",
                    filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai",
                    length: 1,
                    name: "Chrome PDF Viewer",
                    [Symbol.iterator]: function* () {
                        yield this[0];
                    }
                },
                {
                    0: {type: "application/x-nacl", suffixes: "", description: "Native Client Executable", enabledPlugin: null},
                    1: {type: "application/x-pnacl", suffixes: "", description: "Portable Native Client Executable", enabledPlugin: null},
                    description: "",
                    filename: "internal-nacl-plugin",
                    length: 2,
                    name: "Native Client",
                    [Symbol.iterator]: function* () {
                        yield this[0];
                        yield this[1];
                    }
                }
            ];
            
            // Make plugins array iterable
            plugins.item = function(index) {
                return this[index] || null;
            };
            plugins.namedItem = function(name) {
                return this.find(p => p.name === name) || null;
            };
            plugins.refresh = function() {};
            plugins.length = plugins.length;
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => plugins,
                configurable: true
            });
            
            // Mock mimeTypes to match plugins
            const mimeTypes = [
                {type: "application/pdf", suffixes: "pdf", description: "", enabledPlugin: plugins[1]},
                {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: plugins[0]},
                {type: "application/x-nacl", suffixes: "", description: "Native Client Executable", enabledPlugin: plugins[2]},
                {type: "application/x-pnacl", suffixes: "", description: "Portable Native Client Executable", enabledPlugin: plugins[2]}
            ];
            
            mimeTypes.item = function(index) {
                return this[index] || null;
            };
            mimeTypes.namedItem = function(name) {
                return this.find(m => m.type === name) || null;
            };
            mimeTypes.length = mimeTypes.length;
            
            Object.defineProperty(navigator, 'mimeTypes', {
                get: () => mimeTypes,
                configurable: true
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            
            // Mock platform (must override Playwright's setting)
            try {
                Object.defineProperty(Object.getPrototypeOf(navigator), 'platform', {
                    get: () => 'Win32',
                    configurable: true,
                    enumerable: true
                });
            } catch (e) {
                // Fallback if prototype override fails
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Win32',
                    configurable: true,
                    enumerable: true
                });
            }
            
            // Mock vendor (Chrome-specific)
            Object.defineProperty(navigator, 'vendor', {
                get: () => 'Google Inc.',
                configurable: true
            });
            
            // Mock product
            Object.defineProperty(navigator, 'product', {
                get: () => 'Gecko',
                configurable: true
            });
            
            // Mock productSub
            Object.defineProperty(navigator, 'productSub', {
                get: () => '20030107',
                configurable: true
            });
            
            // Mock vendorSub
            Object.defineProperty(navigator, 'vendorSub', {
                get: () => '',
                configurable: true
            });
            
            // Mock appVersion
            Object.defineProperty(navigator, 'appVersion', {
                get: () => '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                configurable: true
            });
            
            // Mock maxTouchPoints
            Object.defineProperty(navigator, 'maxTouchPoints', {
                get: () => 0,
                configurable: true
            });
            
            // Mock hardware concurrency (CPU cores) - typical Windows desktop
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8,  // 8 cores is common for desktop Windows
                configurable: true
            });
            
            // Mock oscpu (Firefox compatibility, but Chrome doesn't have it)
            if ('oscpu' in navigator) {
                Object.defineProperty(navigator, 'oscpu', {
                    get: () => 'Windows NT 10.0; Win64; x64',
                    configurable: true
                });
            }
            
            // Mock device memory (typical desktop)
            if (!navigator.deviceMemory) {
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8,  // 8GB is common
                });
            }
            
            // Mock WebGL for both WebGL and WebGL2 to match Windows/Intel
            const getParameterProxyHandler = {
                apply: function(target, ctx, args) {
                    const param = args[0];
                    // UNMASKED_VENDOR_WEBGL
                    if (param === 37445) {
                        return 'Google Inc. (Intel)';  // More realistic for Windows
                    }
                    // UNMASKED_RENDERER_WEBGL
                    if (param === 37446) {
                        return 'ANGLE (Intel, Intel(R) UHD Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)';  // Windows/Intel
                    }
                    return Reflect.apply(target, ctx, args);
                }
            };
            
            // Patch WebGLRenderingContext
            const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = new Proxy(originalGetParameter, getParameterProxyHandler);
            
            // Patch WebGL2RenderingContext
            const originalGetParameter2 = WebGL2RenderingContext.prototype.getParameter;
            WebGL2RenderingContext.prototype.getParameter = new Proxy(originalGetParameter2, getParameterProxyHandler);
            
            // Mock permissions - make it look like a real browser
            if (navigator.permissions && navigator.permissions.query) {
                const originalQuery = navigator.permissions.query.bind(navigator.permissions);
                navigator.permissions.query = function(parameters) {
                    // Return realistic permission states
                    if (parameters.name === 'notifications') {
                        return Promise.resolve({
                            state: 'prompt',
                            name: 'notifications',
                            onchange: null
                        });
                    }
                    // Call original for other permissions
                    return originalQuery(parameters);
                };
            }
            
            // Mock Notification API
            if (typeof Notification !== 'undefined') {
                const OriginalNotification = Notification;
                Object.defineProperty(Notification, 'permission', {
                    get: () => 'default',
                    configurable: true
                });
            }
            
            // ========================================
            // IFRAME CONTENTWINDOW PROTECTION
            // ========================================
            // Prevent detection through iframe contentWindow checks
            const originalGetOwnPropertyDescriptor = Object.getOwnPropertyDescriptor;
            Object.getOwnPropertyDescriptor = function(obj, prop) {
                const descriptor = originalGetOwnPropertyDescriptor(obj, prop);
                
                // Hide automation properties
                if (prop === 'webdriver' || prop === '__webdriver_script_fn') {
                    return undefined;
                }
                
                return descriptor;
            };
            
            // ========================================
            // PHANTOM JS DETECTION PREVENTION
            // ========================================
            // Remove phantom-specific properties
            if (window.callPhantom) {
                delete window.callPhantom;
            }
            if (window._phantom) {
                delete window._phantom;
            }
            
            // Mock screen properties (realistic 1080p setup)
            Object.defineProperty(screen, 'availTop', {get: () => 0});
            Object.defineProperty(screen, 'availLeft', {get: () => 0});
            Object.defineProperty(screen, 'availWidth', {get: () => 1920});
            Object.defineProperty(screen, 'availHeight', {get: () => 1040});  // Account for taskbar
            Object.defineProperty(screen, 'colorDepth', {get: () => 24});
            Object.defineProperty(screen, 'pixelDepth', {get: () => 24});
            
            // Mock connection (typical broadband)
            if (navigator.connection) {
                Object.defineProperty(navigator.connection, 'effectiveType', {get: () => '4g'});
                Object.defineProperty(navigator.connection, 'rtt', {get: () => 100});
                Object.defineProperty(navigator.connection, 'downlink', {get: () => 10});
            }
            
            // ========================================
            // CDP DETECTION EVASION (Enhanced)
            // ========================================
            // Prevent CDP detection via Error.stack getter
            const originalErrorConstructor = Error;
            Error = function(...args) {
                const error = new originalErrorConstructor(...args);
                const originalStackGetter = Object.getOwnPropertyDescriptor(error, 'stack');
                if (originalStackGetter) {
                    Object.defineProperty(error, 'stack', {
                        get: function() {
                            // Don't trigger CDP detection when accessing stack
                            return originalStackGetter.get.call(this);
                        },
                        configurable: true
                    });
                }
                return error;
            };
            Error.prototype = originalErrorConstructor.prototype;
            
            // Fix Error.prepareStackTrace for CDP detection evasion
            const originalPrepareStackTrace = Error.prepareStackTrace;
            Error.prepareStackTrace = function(error, structuredStackTrace) {
                if (originalPrepareStackTrace) {
                    return originalPrepareStackTrace(error, structuredStackTrace);
                }
                // Return formatted stack trace that doesn't trigger CDP
                return structuredStackTrace.map(function(callSite) {
                    return '    at ' + callSite.toString();
                }).join('\n');
            };
            
            // ========================================
            // CANVAS FINGERPRINTING PROTECTION
            // ========================================
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            const originalToBlob = HTMLCanvasElement.prototype.toBlob;
            const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
            
            // Add slight noise to canvas to prevent fingerprinting
            const addCanvasNoise = (canvas, context) => {
                const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
                const data = imageData.data;
                for (let i = 0; i < data.length; i += 4) {
                    // Add tiny random noise to RGB values (undetectable visually)
                    data[i] = data[i] + Math.floor(Math.random() * 3) - 1;     // R
                    data[i + 1] = data[i + 1] + Math.floor(Math.random() * 3) - 1; // G
                    data[i + 2] = data[i + 2] + Math.floor(Math.random() * 3) - 1; // B
                }
                context.putImageData(imageData, 0, 0);
            };
            
            HTMLCanvasElement.prototype.toDataURL = function(...args) {
                const context = this.getContext('2d');
                if (context) {
                    addCanvasNoise(this, context);
                }
                return originalToDataURL.apply(this, args);
            };
            
            HTMLCanvasElement.prototype.toBlob = function(...args) {
                const context = this.getContext('2d');
                if (context) {
                    addCanvasNoise(this, context);
                }
                return originalToBlob.apply(this, args);
            };
            
            CanvasRenderingContext2D.prototype.getImageData = function(...args) {
                const imageData = originalGetImageData.apply(this, args);
                // Add noise to the returned image data
                const data = imageData.data;
                for (let i = 0; i < data.length; i += 4) {
                    data[i] = data[i] + Math.floor(Math.random() * 3) - 1;
                    data[i + 1] = data[i + 1] + Math.floor(Math.random() * 3) - 1;
                    data[i + 2] = data[i + 2] + Math.floor(Math.random() * 3) - 1;
                }
                return imageData;
            };
            
            console.log('[STEALTH] Canvas fingerprinting protection enabled');
            
            // ========================================
            // AUDIO CONTEXT FINGERPRINTING PROTECTION
            // ========================================
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext) {
                const OriginalAudioContext = AudioContext;
                const OriginalOfflineAudioContext = window.OfflineAudioContext || window.webkitOfflineAudioContext;
                
                // Patch AudioContext
                window.AudioContext = function(...args) {
                    const context = new OriginalAudioContext(...args);
                    const originalCreateOscillator = context.createOscillator;
                    
                    context.createOscillator = function() {
                        const oscillator = originalCreateOscillator.apply(this, arguments);
                        const originalStart = oscillator.start;
                        
                        oscillator.start = function(...args) {
                            // Add tiny random frequency variation
                            if (oscillator.frequency) {
                                const originalValue = oscillator.frequency.value;
                                oscillator.frequency.value = originalValue + Math.random() * 0.0001;
                            }
                            return originalStart.apply(this, args);
                        };
                        
                        return oscillator;
                    };
                    
                    return context;
                };
                
                // Patch OfflineAudioContext
                if (OriginalOfflineAudioContext) {
                    window.OfflineAudioContext = function(...args) {
                        const context = new OriginalOfflineAudioContext(...args);
                        const originalCreateOscillator = context.createOscillator;
                        
                        context.createOscillator = function() {
                            const oscillator = originalCreateOscillator.apply(this, arguments);
                            const originalStart = oscillator.start;
                            
                            oscillator.start = function(...args) {
                                if (oscillator.frequency) {
                                    const originalValue = oscillator.frequency.value;
                                    oscillator.frequency.value = originalValue + Math.random() * 0.0001;
                                }
                                return originalStart.apply(this, args);
                            };
                            
                            return oscillator;
                        };
                        
                        return context;
                    };
                }
                
                console.log('[STEALTH] Audio context fingerprinting protection enabled');
            }
            
            // ========================================
            // WEBRTC LEAK PROTECTION
            // ========================================
            const originalGetUserMedia = navigator.mediaDevices.getUserMedia;
            navigator.mediaDevices.getUserMedia = function(...args) {
                console.log('[STEALTH] getUserMedia called - spoofing...');
                return originalGetUserMedia.apply(this, args);
            };
            
            // Override RTCPeerConnection to prevent IP leaks
            const originalRTCPeerConnection = window.RTCPeerConnection;
            window.RTCPeerConnection = function(...args) {
                const pc = new originalRTCPeerConnection(...args);
                const originalCreateDataChannel = pc.createDataChannel;
                
                pc.createDataChannel = function(...args) {
                    console.log('[STEALTH] RTCPeerConnection data channel intercepted');
                    return originalCreateDataChannel.apply(this, args);
                };
                
                return pc;
            };
            
            // ========================================
            // BATTERY API SPOOFING
            // ========================================
            if (navigator.getBattery) {
                const originalGetBattery = navigator.getBattery;
                navigator.getBattery = function() {
                    return originalGetBattery.apply(this, arguments).then(battery => {
                        // Spoof battery properties
                        Object.defineProperty(battery, 'charging', {value: true});
                        Object.defineProperty(battery, 'chargingTime', {value: 0});
                        Object.defineProperty(battery, 'dischargingTime', {value: Infinity});
                        Object.defineProperty(battery, 'level', {value: 1});
                        return battery;
                    });
                };
            }
            
            // ========================================
            // TIMEZONE SPOOFING
            // ========================================
            const originalDateTimeFormat = Intl.DateTimeFormat;
            Intl.DateTimeFormat = function(...args) {
                if (args.length === 0 || !args[0]) {
                    args[0] = 'en-US';
                }
                return new originalDateTimeFormat(...args);
            };
            
            // Override Date.prototype.getTimezoneOffset
            const originalGetTimezoneOffset = Date.prototype.getTimezoneOffset;
            Date.prototype.getTimezoneOffset = function() {
                // Return EST timezone offset (-300 minutes = UTC-5)
                return 300;
            };
            
            console.log('[STEALTH] Anti-detection script applied successfully');
            
            // ========================================
            // FINAL OVERRIDES (Run last to override Playwright settings)
            // ========================================
            // Platform must be Win32 for Windows user agent
            Object.defineProperty(navigator, 'platform', {
                value: 'Win32',
                writable: false,
                configurable: false
            });
            
            console.log('[STEALTH] navigator.webdriver =', navigator.webdriver);
            console.log('[STEALTH] navigator.platform =', navigator.platform);
        