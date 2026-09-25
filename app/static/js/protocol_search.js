(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        var protocolInput = document.querySelector("[data-protocol-mask]");
        if (!protocolInput) return;

        function protocolParts(value) {
            var normalizedValue = String(value || "").toUpperCase();
            var separatorIndex = normalizedValue.indexOf("-");
            var letterSource = normalizedValue;
            var digitSource = "";

            if (separatorIndex !== -1) {
                letterSource = normalizedValue.slice(0, separatorIndex);
                digitSource = normalizedValue.slice(separatorIndex + 1);
            } else {
                var lettersFound = 0;

                for (var index = 0; index < normalizedValue.length; index += 1) {
                    if (/[A-Z]/.test(normalizedValue.charAt(index))) lettersFound += 1;
                    if (lettersFound === 4) {
                        digitSource = normalizedValue.slice(index + 1);
                        break;
                    }
                }
            }

            return {
                letters: (letterSource.match(/[A-Z]/g) || []).join("").slice(0, 4),
                digits: (digitSource.match(/[0-9]/g) || []).join("").slice(0, 12)
            };
        }

        function formatProtocol(value) {
            var parts = protocolParts(value);
            var dateBlock = parts.digits.slice(0, 8);
            var sequenceBlock = parts.digits.slice(8, 12);
            var formattedValue = parts.letters;

            if (dateBlock) formattedValue += "-" + dateBlock;
            if (sequenceBlock) formattedValue += "-" + sequenceBlock;

            return formattedValue;
        }

        function caretPosition(formattedValue, significantCharacters) {
            var currentCount = 0;

            for (var index = 0; index < formattedValue.length; index += 1) {
                if (/[A-Z0-9]/.test(formattedValue.charAt(index))) {
                    currentCount += 1;
                }

                if (currentCount === significantCharacters) return index + 1;
            }

            return formattedValue.length;
        }

        function applyProtocolMask() {
            var originalValue = protocolInput.value;
            var selectionStart = protocolInput.selectionStart;
            var charactersBeforeCaret = protocolParts(
                originalValue.slice(0, selectionStart === null ? originalValue.length : selectionStart)
            );
            var significantCharacters = charactersBeforeCaret.letters.length + charactersBeforeCaret.digits.length;
            var formattedValue = formatProtocol(originalValue);

            protocolInput.value = formattedValue;

            if (document.activeElement === protocolInput && typeof protocolInput.setSelectionRange === "function") {
                var newCaretPosition = caretPosition(formattedValue, significantCharacters);
                protocolInput.setSelectionRange(newCaretPosition, newCaretPosition);
            }
        }

        protocolInput.addEventListener("input", applyProtocolMask);
        applyProtocolMask();
    });
}());
