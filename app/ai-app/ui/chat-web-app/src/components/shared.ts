export const handleContentDownload = (fileName: string, content: string | Blob | MediaSource, mimeType: string = 'plain/text') => {
    const contentBlob = typeof content === "string" ? new Blob([content], {type: mimeType}) : content;
    const url = URL.createObjectURL(contentBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

function openUrlSafely(url: string): boolean {
    try {
        const newWindow = window.open(url, '_blank', 'noopener,noreferrer');
        return newWindow !== null;
    } catch (error) {
        console.error('Failed to open URL:', error);
        return false;
    }
}

interface FileSelectionOptions {
    accept?: string;
    multiple?: boolean;
    maxSize?: number; // in bytes
    maxFiles?: number;
}

function selectFile(accept?: string, multiple?: boolean): Promise<FileList | null> {
    return new Promise((resolve) => {
        const input = document.createElement('input');
        input.type = 'file';

        if (accept) {
            input.accept = accept;
        }

        if (multiple) {
            input.multiple = true;
        }

        input.onchange = () => {
            resolve(input.files);
        };

        input.oncancel = () => {
            resolve(null);
        };

        input.click();
    });
}

async function selectFileAdvanced(options: FileSelectionOptions = {}): Promise<File[]> {
    const {
        accept,
        multiple = false,
        maxSize,
        maxFiles
    } = options;

    const files = await selectFile(accept, multiple);

    if (!files || files.length === 0) {
        return [];
    }

    let fileArray = Array.from(files);

    // Apply file count limit
    if (maxFiles && fileArray.length > maxFiles) {
        alert(`Maximum ${maxFiles} files allowed`);
        fileArray = fileArray.slice(0, maxFiles);
    }

    // Apply size limit
    if (maxSize) {
        const oversizedFiles = fileArray.filter(file => file.size > maxSize);
        if (oversizedFiles.length > 0) {
            alert(`Some files exceed the ${(maxSize / 1024 / 1024).toFixed(1)}MB limit`);
            fileArray = fileArray.filter(file => file.size <= maxSize);
        }
    }

    return fileArray;
}

export const emSize = parseFloat(getComputedStyle(document.body).fontSize);

export {openUrlSafely, selectFile, selectFileAdvanced};
