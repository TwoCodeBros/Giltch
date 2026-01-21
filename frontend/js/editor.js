/**
 * editor.js
 * ACE Editor Controller
 */

window.CodeEditor = {
    editor: null,

    init(elementId) {
        if (!window.ace) {
            console.error("ACE Editor not loaded properly.");
            return;
        }

        this.editor = ace.edit(elementId);
        this.editor.setTheme("ace/theme/textmate"); // Light theme default
        this.editor.session.setMode("ace/mode/python"); // Default language

        // Editor Options
        this.editor.setOptions({
            fontSize: "14px",
            showPrintMargin: false,
            showGutter: true,
            highlightActiveLine: true,
            wrap: true,
            enableBasicAutocompletion: true,
            enableLiveAutocompletion: true
        });

        // Set Default content
        this.resetCode('python');
    },

    setLanguage(lang) {
        let mode = `ace/mode/${lang}`;
        if (lang === 'c' || lang === 'cpp') mode = 'ace/mode/c_cpp';

        this.editor.session.setMode(mode);
        // We no longer auto-reset code here to prevent overwriting question-specific buggy code
    },

    resetCode(lang) {
        const templates = {
            python: "def solve(n):\n    # Write your code here\n    pass\n\nif __name__ == '__main__':\n    print(solve(5))",
            javascript: "function solve(n) {\n    // Write your code here\n    return;\n}\n\nconsole.log(solve(5));",
            java: "public class Solution {\n    public static void main(String[] args) {\n        System.out.println(\"Hello World\");\n    }\n}",
            cpp: "#include <iostream>\nusing namespace std;\n\nint main() {\n    // Write your code here\n    return 0;\n}"
        };
        this.editor.setValue(templates[lang] || "", -1);
    },

    getValue() {
        return this.editor.getValue();
    }
};
