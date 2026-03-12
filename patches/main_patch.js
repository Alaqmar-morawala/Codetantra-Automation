/*
    CodeTantra SEA - Main Process Patch v4
    ======================================
    1. Scan for Electron fuse sentinel (may error - that's OK)
    2. Patch InternalVerifyIntegrity → RET
    3. Patch exit/abort in libc → RET (immortality)
       Uses enumerateExports fallback for IFUNC symbols
*/
(function () {
    const log = (msg) => send({ type: 'MAIN_LOG', data: '[MAIN] ' + msg });
    log('Main Process Patch v4 loading...');

    const mainModule = Process.enumerateModules()[0];
    log('Scanning ' + mainModule.name + ' (' + mainModule.size + ' bytes) for fuse sentinel...');

    // ── Fuse scan (best-effort, errors are OK) ──
    try {
        const sentinel = "dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX";
        const sentinelBytes = [];
        for (let i = 0; i < sentinel.length; i++) {
            sentinelBytes.push(sentinel.charCodeAt(i).toString(16).padStart(2, '0'));
        }
        const pattern = sentinelBytes.join(' ');
        const matches = Memory.scanSync(mainModule.base, mainModule.size, pattern);
        if (matches.length > 0) {
            log('Fuse sentinel found at ' + matches[0].address);
            const fuseStart = matches[0].address.add(sentinel.length);
            try {
                Memory.protect(fuseStart, 16, 'rwx');
                log('Fuse bytes: ' + fuseStart.readByteArray(8));
            } catch (e) {
                log('Fuse access error: ' + e.message);
            }
        } else {
            log('Fuse sentinel not found in main module');
        }
    } catch (e) {
        log('Fuse scan error (non-fatal): ' + e.message);
    }

    // ── Integrity bypass ──
    try {
        const addr = mainModule.base.add(ptr("0x307e570"));
        Memory.protect(addr, 8, 'rwx');
        addr.writeU8(0xc3); // RET
        log('✓ InternalVerifyIntegrity patched');
    } catch (e) {
        log('Integrity patch error: ' + e.message);
    }

    // ── Immortality: patch exit/abort ──
    // Use enumerateExports to find function addresses (handles IFUNC symbols)
    const modules = Process.enumerateModules();
    let libcMod = null;
    for (const m of modules) {
        if (m.name === 'libc.so.6' || m.name.match(/^libc-.*\.so/)) {
            libcMod = m;
            break;
        }
    }

    if (libcMod) {
        log('libc: ' + libcMod.name + ' @ ' + libcMod.base);
        const targets = ['exit', '_exit', 'abort', '_Exit'];

        // Method 1: enumerate all exports and find function types
        let exports = null;
        try {
            exports = libcMod.enumerateExports();
        } catch (e) {
            log('enumerateExports error: ' + e.message);
        }

        for (const fname of targets) {
            let patched = false;

            // Try enumerateExports first (more reliable for IFUNC)
            if (exports) {
                const exp = exports.find(e => e.name === fname && e.type === 'function');
                if (exp) {
                    try {
                        Memory.protect(exp.address, 8, 'rwx');
                        exp.address.writeU8(0xc3);
                        log('✓ ' + fname + ' patched (enum) @ ' + exp.address);
                        patched = true;
                    } catch (e) {
                        log(fname + ' enum write error: ' + e.message);
                    }
                }
            }

            // Fallback: try Module.findExportByName
            if (!patched) {
                try {
                    const addr = Module.findExportByName(libcMod.name, fname);
                    if (addr) {
                        Memory.protect(addr, 8, 'rwx');
                        addr.writeU8(0xc3);
                        log('✓ ' + fname + ' patched (find) @ ' + addr);
                        patched = true;
                    }
                } catch (e) {
                    log(fname + ' find error: ' + e.message);
                }
            }

            // Fallback 2: scan for symbol via enumerateSymbols
            if (!patched) {
                try {
                    const syms = libcMod.enumerateSymbols();
                    const sym = syms.find(s => s.name === fname && s.type === 'function');
                    if (sym) {
                        Memory.protect(sym.address, 8, 'rwx');
                        sym.address.writeU8(0xc3);
                        log('✓ ' + fname + ' patched (sym) @ ' + sym.address);
                        patched = true;
                    }
                } catch (e) {
                    log(fname + ' sym error: ' + e.message);
                }
            }

            if (!patched) {
                log('⚠ ' + fname + ' NOT patched');
            }
        }
    } else {
        log('⚠ libc not found');
    }

    log('Patch v4 loaded.');
})();
