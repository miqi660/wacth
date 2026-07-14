'use strict';

Java.perform(function () {
    const TARGET_CLASS = 'android.bluetooth.IBluetoothGatt$Stub$Proxy';
    const OUT_PATH = '/data/data/com.pow.greenlionplus/cache/static_control_frames.jsonl';
    const OVERLOAD_TYPES = ['int', 'java.lang.String', 'int', 'int', 'int', '[B'];
    const OVERLOAD_TEXT = '(int, java.lang.String, int, int, int, [B)';
    const EXPECTED_LAST_SEQUENCE = 1528;

    const File = Java.use('java.io.File');
    const FileOutputStream = Java.use('java.io.FileOutputStream');
    const JString = Java.use('java.lang.String');

    const startedAtMs = Date.now();
    let protocolOrdinal = 0;
    let binderInvocationOrdinal = 0;
    let byteArrayCandidates = 0;
    let c8Count = 0;
    let c9Count = 0;
    let caCount = 0;
    let malformedC9 = 0;
    let firstC9Ordinal = null;
    let lastC9Ordinal = null;
    let summaryEmitted = false;
    let fallbackScheduled = false;
    const sequenceCounts = {};
    const outOfRangeSequences = [];
    const handleHistogram = {};

    function toUnsignedArray(javaBytes) {
        const source = Java.array('byte', javaBytes);
        const output = new Array(source.length);
        for (let i = 0; i < source.length; i++) output[i] = source[i] & 0xff;
        return output;
    }

    function toHex(bytes) {
        return bytes.map(function (value) {
            return ('0' + value.toString(16)).slice(-2);
        }).join('').toUpperCase();
    }

    function classify(bytes) {
        if (bytes.length < 2 || bytes[0] !== 0xbc) return null;
        if (bytes[1] === 0xc8) return 'C8';
        if (bytes[1] === 0xc9) return 'C9';
        if (bytes[1] === 0xca) return 'CA';
        return null;
    }

    function writeLine(value) {
        const text = JSON.stringify(value) + '\n';
        const encoded = JString.$new(text).getBytes('UTF-8');
        const stream = FileOutputStream.$new(OUT_PATH, true);
        try {
            stream.write(encoded);
            stream.flush();
        } finally {
            stream.close();
        }
    }

    function resetOutput() {
        const file = File.$new(OUT_PATH);
        const parent = file.getParentFile();
        if (parent !== null && !parent.exists()) parent.mkdirs();
        const stream = FileOutputStream.$new(OUT_PATH, false);
        try {
            stream.flush();
        } finally {
            stream.close();
        }
    }

    function checksumValid(bytes, sequence) {
        if (bytes.length < 7) return false;
        let sum = sequence & 0xff;
        sum += (sequence >> 8) & 0xff;
        for (let i = 6; i < bytes.length - 1; i++) sum += bytes[i];
        return (sum & 0xff) === bytes[bytes.length - 1];
    }

    function inspectC9(bytes) {
        const errors = [];
        const sequence = bytes.length >= 6 ? bytes[4] | (bytes[5] << 8) : null;
        if (bytes.length < 7) errors.push('frame_too_short');
        if (bytes.length < 3 || bytes[2] !== 0x02) errors.push('direction_not_02');
        if (bytes.length < 4 || bytes[3] !== bytes.length - 5) errors.push('len_mismatch');
        if (sequence === null) {
            errors.push('sequence_missing');
        } else if (sequence < 0 || sequence > EXPECTED_LAST_SEQUENCE) {
            errors.push('sequence_out_of_range');
        }
        if (sequence !== null && !checksumValid(bytes, sequence)) errors.push('checksum_mismatch');
        return {
            sequence: sequence,
            regionLength: bytes.length >= 6 ? bytes.length - 6 : null,
            checksumValid: sequence !== null && checksumValid(bytes, sequence),
            errors: errors
        };
    }

    function redactedStringArgs(argumentTypes) {
        let count = 0;
        for (let i = 0; i < argumentTypes.length; i++) {
            if (argumentTypes[i] === 'java.lang.String') count++;
        }
        return count;
    }

    function integerArgs(args, argumentTypes) {
        const values = [];
        for (let i = 0; i < argumentTypes.length; i++) {
            if (argumentTypes[i] === 'int') {
                values.push({ argument_index: i, value: args[i] });
            }
        }
        return values;
    }

    function recordProtocolFrame(command, bytes, byteArrayArgumentIndex, overloadIndex,
                                 args, argumentTypes, currentBinderOrdinal) {
        if (summaryEmitted) return;

        protocolOrdinal++;
        const now = Date.now();
        const observedHandle = args[2];
        const observedWriteType = args[3];
        const observedAuthReq = args[4];
        const handleKey = String(observedHandle);
        handleHistogram[handleKey] = (handleHistogram[handleKey] || 0) + 1;

        let c9 = null;
        if (command === 'C8') c8Count++;
        if (command === 'CA') caCount++;
        if (command === 'C9') {
            c9Count++;
            c9 = inspectC9(bytes);
            if (firstC9Ordinal === null) firstC9Ordinal = protocolOrdinal;
            lastC9Ordinal = protocolOrdinal;
            if (c9.errors.length) malformedC9++;
            if (c9.sequence !== null) {
                sequenceCounts[c9.sequence] = (sequenceCounts[c9.sequence] || 0) + 1;
                if (c9.sequence < 0 || c9.sequence > EXPECTED_LAST_SEQUENCE) {
                    outOfRangeSequences.push(c9.sequence);
                }
            }
        }

        const relativePosition = command === 'C9'
            ? 'during_c9'
            : (firstC9Ordinal === null ? 'before_first_c9' : 'after_last_c9');
        const keepFullHex = command !== 'C9' || c9.sequence === 0 || c9.sequence === EXPECTED_LAST_SEQUENCE;
        const duplicateSequence = c9 !== null && c9.sequence !== null &&
            sequenceCounts[c9.sequence] > 1;
        const record = {
            kind: 'frame',
            ordinal: protocolOrdinal,
            binder_invocation_ordinal: currentBinderOrdinal,
            timestamp_unix_ms: now,
            elapsed_ms: now - startedAtMs,
            command: command,
            direction: bytes.length >= 3 ? bytes[2] : null,
            value_length: bytes.length,
            byte_array_argument_index: byteArrayArgumentIndex,
            relative_position: relativePosition,
            address: '<redacted>',
            overload_index: overloadIndex,
            overload: OVERLOAD_TEXT,
            binder_int_args: integerArgs(args, argumentTypes),
            string_args_redacted: redactedStringArgs(argumentTypes),
            observed_handle: observedHandle,
            observed_write_type: observedWriteType,
            observed_auth_req: observedAuthReq,
            frame_hex: keepFullHex ? toHex(bytes) : null,
            sequence: c9 === null ? null : c9.sequence,
            c9_region_length: c9 === null ? null : c9.regionLength,
            checksum_valid: c9 === null ? null : c9.checksumValid,
            duplicate_sequence: duplicateSequence,
            validation_errors: c9 === null ? [] : c9.errors
        };
        writeLine(record);

        if (command === 'C8' || command === 'CA') {
            console.log('[CONTROL] command=' + command +
                        ' ordinal=' + protocolOrdinal +
                        ' len=' + bytes.length +
                        ' handle=' + observedHandle +
                        ' hex=' + toHex(bytes));
        } else if (duplicateSequence) {
            console.log('[C9 ERROR] duplicate seq=' + c9.sequence +
                        ' ordinal=' + protocolOrdinal);
        } else if (c9.errors.length) {
            console.log('[C9 ERROR] ordinal=' + protocolOrdinal +
                        ' seq=' + c9.sequence +
                        ' errors=' + c9.errors.join(','));
        } else if (c9.sequence === 0 || c9.sequence % 128 === 0 ||
                   c9.sequence === EXPECTED_LAST_SEQUENCE) {
            console.log('[C9] seq=' + c9.sequence +
                        ' ordinal=' + protocolOrdinal +
                        ' len=' + bytes.length +
                        ' region=' + c9.regionLength +
                        ' handle=' + observedHandle);
        }

        if (command === 'CA') {
            emitSummary('CA');
        } else if (command === 'C9' && c9.sequence === EXPECTED_LAST_SEQUENCE && !fallbackScheduled) {
            fallbackScheduled = true;
            setTimeout(function () {
                Java.perform(function () { emitSummary('seq1528-timeout-5s'); });
            }, 5000);
        }
    }

    function buildSummary(reason) {
        const unique = Object.keys(sequenceCounts).map(function (key) {
            return parseInt(key, 10);
        }).sort(function (a, b) { return a - b; });
        const inRange = unique.filter(function (sequence) {
            return sequence >= 0 && sequence <= EXPECTED_LAST_SEQUENCE;
        });
        const missing = [];
        const duplicates = [];
        for (let sequence = 0; sequence <= EXPECTED_LAST_SEQUENCE; sequence++) {
            if (!(sequence in sequenceCounts)) missing.push(sequence);
        }
        unique.forEach(function (sequence) {
            if (sequenceCounts[sequence] > 1) duplicates.push(sequence);
        });
        return {
            kind: 'summary',
            reason: reason,
            total_binder_invocations: binderInvocationOrdinal,
            byte_array_candidates: byteArrayCandidates,
            protocol_frames: protocolOrdinal,
            c8_count: c8Count,
            c9_count: c9Count,
            ca_count: caCount,
            unique_sequences: inRange.length,
            sequence_range: inRange.length ? inRange[0] + '..' + inRange[inRange.length - 1] : null,
            expected_sequence_range: '0..1528',
            first_c9_ordinal: firstC9Ordinal,
            last_c9_ordinal: lastC9Ordinal,
            missing_count: missing.length,
            missing_sequences: missing,
            duplicates: duplicates.length,
            duplicate_sequences: duplicates,
            malformed_c9: malformedC9,
            out_of_range_sequences: outOfRangeSequences,
            handle_histogram: handleHistogram,
            address_policy: 'redacted',
            capture_filter: 'protocol bytes first; no handle prefilter'
        };
    }

    function emitSummary(reason) {
        if (summaryEmitted) return null;
        summaryEmitted = true;
        const summary = buildSummary(reason);
        writeLine(summary);
        console.log('');
        console.log('=== STATIC CONTROL FRAME CAPTURE ===');
        console.log('[SUMMARY] reason=' + summary.reason);
        console.log('[SUMMARY] totalBinderInvocations=' + summary.total_binder_invocations);
        console.log('[SUMMARY] byteArrayCandidates=' + summary.byte_array_candidates);
        console.log('[SUMMARY] protocolFrames=' + summary.protocol_frames);
        console.log('[SUMMARY] c8Count=' + summary.c8_count);
        console.log('[SUMMARY] c9Count=' + summary.c9_count);
        console.log('[SUMMARY] caCount=' + summary.ca_count);
        console.log('[SUMMARY] uniqueSeq=' + summary.unique_sequences);
        console.log('[SUMMARY] sequenceRange=' + summary.sequence_range);
        console.log('[SUMMARY] missing=' + summary.missing_count);
        console.log('[SUMMARY] duplicates=' + summary.duplicates);
        console.log('[SUMMARY] malformedC9=' + summary.malformed_c9);
        console.log('[SUMMARY] outOfRange=' + summary.out_of_range_sequences.length);
        console.log('[SUMMARY] firstC9Ordinal=' + summary.first_c9_ordinal +
                    ' lastC9Ordinal=' + summary.last_c9_ordinal);
        console.log('[SUMMARY] handleHistogram=' + JSON.stringify(summary.handle_histogram));
        console.log('[SUMMARY] output=' + OUT_PATH);
        console.log('[SUMMARY] addressPolicy=' + summary.address_policy);
        console.log('[SUMMARY] captureFilter=' + summary.capture_filter);
        console.log('====================================');
        console.log('');
        return summary;
    }

    let ProxyClass;
    try {
        ProxyClass = Java.use(TARGET_CLASS);
    } catch (error) {
        console.log('[ERROR] cannot load ' + TARGET_CLASS + ': ' + error);
        return;
    }

    if (!ProxyClass.writeCharacteristic) {
        console.log('[ERROR] writeCharacteristic not found on ' + TARGET_CLASS);
        return;
    }

    resetOutput();
    let hookedOverloads = 0;
    ProxyClass.writeCharacteristic.overloads.forEach(function (overload, index) {
        const argumentTypes = overload.argumentTypes.map(function (type) {
            return type.className;
        });
        console.log('[HOOK] overload[' + index + '] (' + argumentTypes.join(', ') + ')');
        const exactMatch = argumentTypes.length === OVERLOAD_TYPES.length && argumentTypes.every(
            function (type, typeIndex) { return type === OVERLOAD_TYPES[typeIndex]; }
        );
        if (!exactMatch) return;

        hookedOverloads++;
        overload.implementation = function () {
            const args = [].slice.call(arguments);
            binderInvocationOrdinal++;
            const currentBinderOrdinal = binderInvocationOrdinal;
            try {
                for (let argumentIndex = 0; argumentIndex < args.length; argumentIndex++) {
                    if (argumentTypes[argumentIndex] !== '[B' &&
                        argumentTypes[argumentIndex] !== 'byte[]') continue;
                    if (args[argumentIndex] === null) continue;
                    byteArrayCandidates++;
                    const bytes = toUnsignedArray(args[argumentIndex]);
                    const command = classify(bytes);
                    if (command === null) continue;
                    recordProtocolFrame(
                        command,
                        bytes,
                        argumentIndex,
                        index,
                        args,
                        argumentTypes,
                        currentBinderOrdinal
                    );
                }
            } catch (error) {
                console.log('[CAPTURE ERROR] ' + error);
            }
            return overload.call.apply(overload, [this].concat(args));
        };
    });

    if (hookedOverloads !== 1) {
        console.log('[ERROR] expected exactly one verified overload, hooked=' + hookedOverloads);
        return;
    }

    rpc.exports = {
        summary: function () {
            let result = null;
            Java.perform(function () { result = emitSummary('manual'); });
            return result;
        }
    };

    console.log('[OK] read-only protocol-first Binder control-frame capture installed');
    console.log('[OK] layer=' + TARGET_CLASS + '.writeCharacteristic');
    console.log('[OK] overload=' + OVERLOAD_TEXT);
    console.log('[OK] captureFilter=protocol bytes first; no handle prefilter');
    console.log('[OK] addressPolicy=redacted');
    console.log('[OK] output=' + OUT_PATH);
});
