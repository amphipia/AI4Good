const fileInput =
    document.getElementById("fileInput");

const dropZone =
    document.getElementById("dropZone");

const previewSection =
    document.getElementById("previewSection");

const resultsSection =
    document.getElementById("resultsSection");

const protectedSection =
    document.getElementById("protectedSection");

const scanStatus =
    document.getElementById("scanStatus");

const scanButton =
    document.getElementById("scanButton");

const protectButton =
    document.getElementById("protectButton");

const metadataResults =
    document.getElementById("metadataResults");

const faceResults =
    document.getElementById("faceResults");

const canvas =
    document.getElementById("imageCanvas");

const ctx =
    canvas.getContext("2d");

const protectedImage =
    document.getElementById("protectedImage");

const downloadButton =
    document.getElementById("downloadButton");

const protectionSummary =
    document.getElementById(
        "protectionSummary"
    );

const qrResults =
    document.getElementById(
        "qrResults"
    );

const textResults =
    document.getElementById(
        "textResults"
    );

const plateResults =
    document.getElementById(
        "plateResults"
    );
	
let selectedFile = null;

let originalImage = new Image();

let detectedFaces = [];

let lastMetadataScan = null;
let lastFaceScan = null;

let detectedQRCodes = [];
let lastQRScan = null;

let detectedPrivacyText = [];
let lastTextScan = null;

let detectedPlates = [];
let lastPlateScan = null;

fileInput.addEventListener(
    "change",
    event => {

        const file =
            event.target.files[0];

        if (file) {
            loadImage(file);
        }

    }
);


dropZone.addEventListener(
    "dragover",
    event => {

        event.preventDefault();

        dropZone.classList.add(
            "dragging"
        );

    }
);


dropZone.addEventListener(
    "dragleave",
    () => {

        dropZone.classList.remove(
            "dragging"
        );

    }
);


dropZone.addEventListener(
    "drop",
    event => {

        event.preventDefault();

        dropZone.classList.remove(
            "dragging"
        );

        const file =
            event.dataTransfer.files[0];

        if (file) {
            loadImage(file);
        }

    }
);

function updateScanStatus(
    id,
    label,
    success = true
) {

    const element =
        document.getElementById(id);

    if (!element) {
        return;
    }

    if (success) {

        element.innerHTML =
            `✓ ${label}`;

        element.classList.add(
            "scan-complete"
        );

    }
    else {

        element.innerHTML =
            `⚠ ${label}`;

        element.classList.add(
            "scan-error"
        );

    }
}

function resetScanStatus() {

    const items = [
        ["statusMetadata", "Metadata"],
        ["statusFaces", "Faces"],
        ["statusQR", "QR codes"],
        [
            "statusText",
            "Personal information"
        ],
        [
            "statusPlates",
            "License plates"
        ]
    ];

    items.forEach(
        ([id, label]) => {

            const element =
                document.getElementById(id);

            if (!element) {
                return;
            }

            element.textContent =
                `⟳ ${label}`;

            element.classList.remove(
                "scan-complete",
                "scan-error"
            );
        }
    );
}

async function scanText(file) {

    const formData =
        new FormData();

    formData.append(
        "file",
        file
    );


    const response =
        await fetch(
            "/api/text/scan",
            {
                method: "POST",
                body: formData
            }
        );


    if (!response.ok) {

        throw new Error(
            "Text scan failed."
        );

    }


    return await response.json();
}

async function scanPlates(file) {

    const formData =
        new FormData();

    formData.append(
        "file",
        file
    );


    const response =
        await fetch(
            "/api/plates/scan",
            {
                method: "POST",
                body: formData
            }
        );


    if (!response.ok) {

        const errorText =
            await response.text();

        throw new Error(
            `License plate scan failed: ${errorText}`
        );

    }


    return await response.json();
}

function displayPlates(data) {

    const count =
        data.plate_count || 0;


    if (count === 0) {

        plateResults.innerHTML = `
            <div class="clear">
                ✓ No license plates detected
            </div>
        `;

        return;
    }


    let html = `
        <div class="detected">
            ${count}
            possible license plate${
                count === 1
                    ? ""
                    : "s"
            }
            detected
        </div>

        <div class="face-selection-actions">

            <button
                type="button"
                id="selectAllPlates"
                class="small-button"
            >
                Select all
            </button>

            <button
                type="button"
                id="clearAllPlates"
                class="small-button"
            >
                Clear all
            </button>

        </div>
    `;


    data.plates.forEach(
        (plate, index) => {

            html += `
                <label class="plate-option">

                    <input
                        type="checkbox"
                        class="plate-checkbox"
                        data-plate-index="${index}"
                        checked
                    >

                    <span>

                        <strong>
                            Plate ${index + 1}
                        </strong>

                        <br>

                        Confidence:
                        ${(
                            plate.confidence * 100
                        ).toFixed(1)}%

                    </span>

                </label>
            `;

        }
    );


    plateResults.innerHTML =
        html;


    document
        .getElementById(
            "selectAllPlates"
        )
        .addEventListener(
            "click",
            () => {

                document
                    .querySelectorAll(
                        ".plate-checkbox"
                    )
                    .forEach(
                        checkbox => {
                            checkbox.checked =
                                true;
                        }
                    );

            }
        );


    document
        .getElementById(
            "clearAllPlates"
        )
        .addEventListener(
            "click",
            () => {

                document
                    .querySelectorAll(
                        ".plate-checkbox"
                    )
                    .forEach(
                        checkbox => {
                            checkbox.checked =
                                false;
                        }
                    );

            }
        );
}

function getSelectedPlates() {

    const selected = [];


    document
        .querySelectorAll(
            ".plate-checkbox"
        )
        .forEach(
            checkbox => {

                if (
                    !checkbox.checked
                ) {
                    return;
                }


                const index =
                    Number(
                        checkbox.dataset
                            .plateIndex
                    );


                const plate =
                    detectedPlates[
                        index
                    ];


                if (plate) {

                    selected.push({
                        x:
                            plate.x,

                        y:
                            plate.y,

                        width:
                            plate.width,

                        height:
                            plate.height
                    });

                }

            }
        );


    return selected;
}

function formatPrivacyType(
    type
) {

    const names = {

        email_address:
            "Email address",

        phone_number:
            "Phone number",

        street_address:
            "Street address",

        ssn_like:
            "SSN-like number",

        payment_card_like:
            "Payment card number",

        web_address:
            "Web address"
    };


    return names[type]
        || type;
}


function displayText(data) {

    const count =
        data.privacy_text_count || 0;


    if (count === 0) {

        textResults.innerHTML = `
            <div class="clear">
                ✓ No obvious private text detected
            </div>
        `;

        return;
    }


    let html = `
        <div class="detected">
            ${count}
            possible private text
            region${
                count === 1
                    ? ""
                    : "s"
            }
            detected
        </div>

        <div class="face-selection-actions">

            <button
                type="button"
                id="selectAllText"
                class="small-button"
            >
                Select all
            </button>

            <button
                type="button"
                id="clearAllText"
                class="small-button"
            >
                Clear all
            </button>

        </div>
    `;


    data.privacy_items.forEach(
        (item, index) => {

            const typeNames =
                item.privacy_types
                    .map(
                        formatPrivacyType
                    )
                    .join(", ");


            html += `
                <label class="text-option">

                    <input
                        type="checkbox"
                        class="text-checkbox"
                        data-text-index="${index}"
                        checked
                    >

                    <span>

                        <strong>
                            ${escapeHtml(
                                typeNames
                            )}
                        </strong>

                        <br>

                        <span class="sensitive-value">
                            ${escapeHtml(
                                item.text
                            )}
                        </span>

                    </span>

                </label>
            `;

        }
    );


    textResults.innerHTML =
        html;


    document
        .getElementById(
            "selectAllText"
        )
        .addEventListener(
            "click",
            () => {

                document
                    .querySelectorAll(
                        ".text-checkbox"
                    )
                    .forEach(
                        checkbox => {
                            checkbox.checked =
                                true;
                        }
                    );

            }
        );


    document
        .getElementById(
            "clearAllText"
        )
        .addEventListener(
            "click",
            () => {

                document
                    .querySelectorAll(
                        ".text-checkbox"
                    )
                    .forEach(
                        checkbox => {
                            checkbox.checked =
                                false;
                        }
                    );

            }
        );
}

function getSelectedText() {

    const selected = [];


    document
        .querySelectorAll(
            ".text-checkbox"
        )
        .forEach(
            checkbox => {

                if (
                    !checkbox.checked
                ) {
                    return;
                }


                const index =
                    Number(
                        checkbox.dataset
                            .textIndex
                    );


                const item =
                    detectedPrivacyText[
                        index
                    ];


                if (item) {

                    selected.push({
                        points:
                            item.points
                    });

                }

            }
        );


    return selected;
}

function loadImage(file) {

    selectedFile = file;

    detectedFaces = [];

    resultsSection.classList.add(
        "hidden"
    );

    protectedSection.classList.add(
        "hidden"
    );

    const imageURL =
        URL.createObjectURL(file);


    originalImage.onload = () => {

        canvas.width =
            originalImage.naturalWidth;

        canvas.height =
            originalImage.naturalHeight;

        ctx.drawImage(
            originalImage,
            0,
            0
        );

        previewSection.classList.remove(
            "hidden"
        );

    };


    originalImage.src = imageURL;
}


scanButton.addEventListener(
    "click",
    async () => {

        if (!selectedFile) {
            return;
        }

        scanStatus.classList.remove(
            "hidden"
        );
		
		resetScanStatus();

		requestAnimationFrame(() => {

			scanStatus.scrollIntoView({
				behavior: "smooth",
				block: "center"
			});

			scanStatus.focus({
				preventScroll: true
			});

		});		

        resultsSection.classList.add(
            "hidden"
        );

        try {

            const [
                metadata,
                faces,
				qr,
				text,
				plates
            ] = await Promise.all([
                scanMetadata(
                    selectedFile
				).then(result => {

					updateScanStatus(
						"statusMetadata",
						"Metadata"
					);

					return result;
				}),

                scanFaces(
                    selectedFile
				).then(result => {

					updateScanStatus(
						"statusFaces",
						"Faces"
					);

					return result;
				}),
				
				scanQR(
					selectedFile
				).then(result => {

					updateScanStatus(
						"statusQR",
						"QR codes"
					);

					return result;
				}),
				
				scanText(
					selectedFile
				).then(result => {

					updateScanStatus(
						"statusText",
						"Personal information"
					);

					return result;
				}),
				
				scanPlates(
					selectedFile
				).then(result => {

					updateScanStatus(
						"statusPlates",
						"License plates"
					);

					return result;
				})				
            ]);


            displayMetadata(
                metadata
            );

            displayFaces(
                faces
            );
			
			displayQR(
				qr
			);
			
			displayText(
				text
			);
			displayPlates(
				plates
			);

			lastMetadataScan = metadata;
			lastFaceScan = faces;
			lastQRScan = qr;
			lastTextScan = text;
			lastPlateScan = plates;

            detectedFaces = faces.faces || [];
				
			detectedQRCodes = qr.qr_codes || [];
			
			detectedPrivacyText = text.privacy_items || [];

			detectedPlates = plates.plates || [];			

            //drawFaceBoxes(
                //detectedFaces
            //);
			drawDetections(
				detectedFaces,
				detectedQRCodes,
				detectedPrivacyText,
				detectedPlates
			);


            resultsSection.classList.remove(
                "hidden"
            );
			resultsSection.scrollIntoView({
				behavior: "smooth",
				block: "start"
			});			

        }
        catch (error) {

            console.error(error);

            alert(
                "Scan failed. Check the API console."
            );

        }
        finally {

            scanStatus.classList.add(
                "hidden"
            );

        }

    }
);


async function scanMetadata(file) {

    const formData =
        new FormData();

    formData.append(
        "file",
        file
    );


    const response =
        await fetch(
            "/api/metadata/scan",
            {
                method: "POST",
                body: formData
            }
        );


    if (!response.ok) {

        throw new Error(
            "Metadata scan failed."
        );

    }


    return await response.json();
}


async function scanFaces(file) {

    const formData =
        new FormData();

    formData.append(
        "file",
        file
    );


    const response =
        await fetch(
            "/api/faces/scan",
            {
                method: "POST",
                body: formData
            }
        );


    if (!response.ok) {

        throw new Error(
            "Face scan failed."
        );

    }


    return await response.json();
}

async function scanQR(file) {

    const formData =
        new FormData();

    formData.append(
        "file",
        file
    );


    const response =
        await fetch(
            "/api/qr/scan",
            {
                method: "POST",
                body: formData
            }
        );


    if (!response.ok) {

        throw new Error(
            "QR scan failed."
        );

    }


    return await response.json();
}

function displayMetadata(data) {

    let html = "";


    if (!data.metadata_found) {

        html += `
            <div class="clear">
                ✓ No EXIF metadata detected
            </div>
        `;

        metadataResults.innerHTML =
            html;

        return;
    }


    if (data.gps_found) {

        html += `
            <div class="result-row detected">
                📍 GPS location embedded
            </div>
        `;

    }
    else {

        html += `
            <div class="result-row clear">
                ✓ No GPS coordinates found
            </div>
        `;

    }


    if (data.metadata) {

        for (
            const [key, value]
            of Object.entries(
                data.metadata
            )
        ) {

            html += `
                <div class="result-row">
                    <strong>
                        ${escapeHtml(key)}
                    </strong>
                    <br>
                    ${escapeHtml(
                        String(value)
                    )}
                </div>
            `;

        }

    }


    metadataResults.innerHTML =
        html;
}


function displayFaces(data) {

    const count =
        data.face_count || 0;

    if (count === 0) {

        faceResults.innerHTML = `
            <div class="clear">
                ✓ No faces detected
            </div>
        `;

        return;
    }


    let html = `
        <div class="detected">
            ${count}
            possible face${
                count === 1
                    ? ""
                    : "s"
            }
            detected
        </div>

        <div class="face-selection-actions">

            <button
                type="button"
                id="selectAllFaces"
                class="small-button"
            >
                Select all
            </button>

            <button
                type="button"
                id="clearAllFaces"
                class="small-button"
            >
                Clear all
            </button>

        </div>
    `;


    data.faces.forEach(
        (face, index) => {

            html += `
                <label class="face-option">

                    <input
                        type="checkbox"
                        class="face-checkbox"
                        data-face-index="${index}"
                        checked
                    >

                    <span>
                        <strong>
                            Face ${index + 1}
                        </strong>

                        <br>

                        Confidence:
                        ${(
                            face.confidence * 100
                        ).toFixed(1)}%
                    </span>

                </label>
            `;

        }
    );


    faceResults.innerHTML =
        html;


    document
        .getElementById(
            "selectAllFaces"
        )
        .addEventListener(
            "click",
            () => {

                document
                    .querySelectorAll(
                        ".face-checkbox"
                    )
                    .forEach(
                        checkbox => {
                            checkbox.checked =
                                true;
                        }
                    );

            }
        );


    document
        .getElementById(
            "clearAllFaces"
        )
        .addEventListener(
            "click",
            () => {

                document
                    .querySelectorAll(
                        ".face-checkbox"
                    )
                    .forEach(
                        checkbox => {
                            checkbox.checked =
                                false;
                        }
                    );

            }
        );
}

function displayQR(data) {

    const count =
        data.qr_count || 0;


    if (count === 0) {

        qrResults.innerHTML = `
            <div class="clear">
                ✓ No QR codes detected
            </div>
        `;

        return;
    }


    let html = `
        <div class="detected">
            ${count}
            QR code${
                count === 1
                    ? ""
                    : "s"
            }
            detected
        </div>

        <div class="face-selection-actions">

            <button
                type="button"
                id="selectAllQR"
                class="small-button"
            >
                Select all
            </button>

            <button
                type="button"
                id="clearAllQR"
                class="small-button"
            >
                Clear all
            </button>

        </div>
    `;


    data.qr_codes.forEach(
        (qr, index) => {

            html += `
                <div class="qr-option">

                    <label>

                        <input
                            type="checkbox"
                            class="qr-checkbox"
                            data-qr-index="${index}"
                            checked
                        >

                        <strong>
                            QR ${index + 1}
                        </strong>

                    </label>

                    <div class="qr-type">
                        Contains:
                        ${escapeHtml(
                            qr.content_type
                        )}
                    </div>
            `;


            if (
                qr.decoded_available
            ) {

                html += `
                    <button
                        type="button"
                        class="show-qr-button"
                        data-qr-show="${index}"
                    >
                        Show decoded content
                    </button>

                    <div
                        id="qrContent${index}"
                        class="qr-content hidden"
                    >
                        ${escapeHtml(
                            qr.decoded
                        )}
                    </div>
                `;

            }
            else {

                html += `
                    <div class="qr-type">
                        Content could not
                        be decoded.
                    </div>
                `;

            }


            html += `
                </div>
            `;

        }
    );


    qrResults.innerHTML =
        html;


    document
        .getElementById(
            "selectAllQR"
        )
        .addEventListener(
            "click",
            () => {

                document
                    .querySelectorAll(
                        ".qr-checkbox"
                    )
                    .forEach(
                        checkbox => {
                            checkbox.checked =
                                true;
                        }
                    );

            }
        );


    document
        .getElementById(
            "clearAllQR"
        )
        .addEventListener(
            "click",
            () => {

                document
                    .querySelectorAll(
                        ".qr-checkbox"
                    )
                    .forEach(
                        checkbox => {
                            checkbox.checked =
                                false;
                        }
                    );

            }
        );


    document
        .querySelectorAll(
            ".show-qr-button"
        )
        .forEach(
            button => {

                button.addEventListener(
                    "click",
                    () => {

                        const index =
                            button.dataset
                                .qrShow;

                        const content =
                            document.getElementById(
                                `qrContent${index}`
                            );

                        const hidden =
                            content.classList
                                .contains(
                                    "hidden"
                                );


                        content.classList.toggle(
                            "hidden"
                        );


                        button.textContent =
                            hidden
                                ? "Hide decoded content"
                                : "Show decoded content";

                    }
                );

            }
        );
}

function getSelectedFaces() {

    const selectedFaces = [];

    document
        .querySelectorAll(
            ".face-checkbox"
        )
        .forEach(
            checkbox => {

                if (
                    !checkbox.checked
                ) {
                    return;
                }

                const index =
                    Number(
                        checkbox.dataset
                            .faceIndex
                    );

                const face =
                    detectedFaces[
                        index
                    ];

                if (face) {

                    selectedFaces.push({
                        x: face.x,
                        y: face.y,
                        width:
                            face.width,
                        height:
                            face.height
                    });

                }

            }
        );

    return selectedFaces;
}

function getSelectedQRCodes() {

    const selected = [];


    document
        .querySelectorAll(
            ".qr-checkbox"
        )
        .forEach(
            checkbox => {

                if (
                    !checkbox.checked
                ) {
                    return;
                }


                const index =
                    Number(
                        checkbox.dataset
                            .qrIndex
                    );


                const qr =
                    detectedQRCodes[
                        index
                    ];


                if (qr) {

                    selected.push({
                        points:
                            qr.points
                    });

                }

            }
        );


    return selected;
}

function drawDetections(
    faces,
    qrCodes, privacyText, plates
) {

    ctx.clearRect(
        0,
        0,
        canvas.width,
        canvas.height
    );


    ctx.drawImage(
        originalImage,
        0,
        0
    );


	// The canvas contains the full-resolution image,
	// but CSS may display it much smaller.
	//
	// Example:
	// canvas.width = 4000
	// displayed width = 800
	//
	// displayScale = 0.20

	const displayScale =
		canvas.clientWidth /
		canvas.width;


	// Make labels appear about 18px tall
	// on the user's screen regardless of image size.

	const desiredScreenFontSize =
		18;

	const canvasFontSize =
		desiredScreenFontSize /
		displayScale;


	// Make box borders appear about 3px thick
	// on the screen.

	const desiredScreenLineWidth =
		3;

	const canvasLineWidth =
		desiredScreenLineWidth /
		displayScale;


	ctx.lineWidth =
		canvasLineWidth;


	ctx.font =
		`bold ${canvasFontSize}px Arial`;


    // --------------------------------
    // FACES
    // --------------------------------

    ctx.strokeStyle =
        "#00ff80";

    ctx.fillStyle =
        "#00ff80";


    faces.forEach(
        (face, index) => {

            ctx.strokeRect(
                face.x,
                face.y,
                face.width,
                face.height
            );


            ctx.fillText(
                `Face ${index + 1}`,
                face.x,
                Math.max(
                    25,
                    face.y - 8
                )
            );

        }
    );


    // --------------------------------
    // QR CODES
    // --------------------------------

    ctx.strokeStyle =
        "#00bfff";

    ctx.fillStyle =
        "#00bfff";


    qrCodes.forEach(
        (qr, index) => {

            const points =
                qr.points || [];


            if (
                points.length < 4
            ) {
                return;
            }


            ctx.beginPath();

            ctx.moveTo(
                points[0].x,
                points[0].y
            );


            for (
                let i = 1;
                i < points.length;
                i++
            ) {

                ctx.lineTo(
                    points[i].x,
                    points[i].y
                );

            }


            ctx.closePath();

            ctx.stroke();


            ctx.fillText(
                `QR ${index + 1}`,
                points[0].x,
                Math.max(
                    25,
                    points[0].y - 8
                )
            );

        }
    );
	
	// --------------------------------
	// PRIVATE TEXT / PII
	// --------------------------------

	ctx.strokeStyle =
		"#ff4d4d";

	ctx.fillStyle =
		"#ff4d4d";


	privacyText.forEach(
		(item, index) => {

			const points =
				item.points || [];

			if (
				points.length < 4
			) {
				return;
			}


			ctx.beginPath();

			ctx.moveTo(
				points[0].x,
				points[0].y
			);


			for (
				let i = 1;
				i < points.length;
				i++
			) {

				ctx.lineTo(
					points[i].x,
					points[i].y
				);

			}


			ctx.closePath();

			ctx.stroke();


			let label =
				`Private text ${index + 1}`;


			if (
				item.privacy_types
				&& item.privacy_types.length > 0
			) {

				label =
					formatPrivacyType(
						item.privacy_types[0]
					);

			}


			ctx.fillText(
				label,
				points[0].x,
				Math.max(
					25,
					points[0].y - 8
				)
			);

		}
	);	

	// --------------------------------
	// LICENSE PLATES
	// --------------------------------

	ctx.strokeStyle =
		"#ff00ff";

	ctx.fillStyle =
		"#ff00ff";


	plates.forEach(
		(plate, index) => {

			ctx.strokeRect(
				plate.x,
				plate.y,
				plate.width,
				plate.height
			);


			ctx.fillText(
				`Plate ${index + 1}`,
				plate.x,
				Math.max(
					25,
					plate.y - 8
				)
			);

		}
	);	
}

function drawFaceBoxes(faces) {

    ctx.clearRect(
        0,
        0,
        canvas.width,
        canvas.height
    );


    ctx.drawImage(
        originalImage,
        0,
        0
    );


    ctx.lineWidth =
        Math.max(
            3,
            canvas.width / 500
        );


    ctx.strokeStyle =
        "#00ff80";


    ctx.font =
        `${Math.max(
            18,
            canvas.width / 45
        )}px Arial`;


    faces.forEach(
        (face, index) => {

            ctx.strokeRect(
                face.x,
                face.y,
                face.width,
                face.height
            );


            ctx.fillStyle =
                "#00ff80";


            ctx.fillText(
                `Face ${index + 1}`,
                face.x,
                Math.max(
                    25,
                    face.y - 8
                )
            );

        }
    );
}


protectButton.addEventListener(
    "click",
    async () => {

        if (!selectedFile) {
            return;
        }


        protectButton.disabled =
            true;

        protectButton.textContent =
            "Protecting...";


        try {

            /*
             * STEP 1:
             * Remove metadata.
             */

            const metadataForm =
                new FormData();

            metadataForm.append(
                "file",
                selectedFile
            );


            const metadataResponse =
                await fetch(
                    "/api/metadata/sanitize",
                    {
                        method: "POST",
                        body: metadataForm
                    }
                );


            if (!metadataResponse.ok) {

                throw new Error(
                    "Metadata sanitization failed."
                );

            }


            const metadataCleanBlob =
                await metadataResponse.blob();


            /*
             * STEP 2:
             * Send metadata-clean copy
             * through face blurring.
             */

            const faceForm =
                new FormData();


            faceForm.append(
                "file",
                metadataCleanBlob,
                "PrivChk_clean.jpg"
            );
			
			const selectedFaces =
			    getSelectedFaces();


			faceForm.append(
			    "selected_faces",
    			JSON.stringify(
			        selectedFaces
    			)
			);


            const faceResponse =
                await fetch(
                    "/api/faces/sanitize",
                    {
                        method: "POST",
                        body: faceForm
                    }
                );


            if (!faceResponse.ok) {

                throw new Error(
                    "Face sanitization failed."
                );

            }


            const faceProtectedBlob =
                await faceResponse.blob();

			/*
			 * STEP 3:
			 * Blur selected QR codes.
			 */

			const qrForm =
				new FormData();


			qrForm.append(
				"file",
				faceProtectedBlob,
				"privchk_faces_clean.jpg"
			);


			const selectedQR =
				getSelectedQRCodes();


			qrForm.append(
				"selected_qr_codes",
				JSON.stringify(
					selectedQR
				)
			);


			const qrResponse =
				await fetch(
					"/api/qr/sanitize",
					{
						method: "POST",
						body: qrForm
					}
				);


			if (!qrResponse.ok) {

				throw new Error(
					"QR sanitization failed."
				);

			}


			const qrProtectedBlob =
				await qrResponse.blob();

			/*
			 * STEP 4:
			 * Redact selected private text.
			 */

			const textForm =
				new FormData();


			textForm.append(
				"file",
				qrProtectedBlob,
				"privchk_qr_clean.jpg"
			);


			const selectedText =
				getSelectedText();


			textForm.append(
				"selected_text",
				JSON.stringify(
					selectedText
				)
			);


			const textResponse =
				await fetch(
					"/api/text/sanitize",
					{
						method: "POST",
						body: textForm
					}
				);


			if (!textResponse.ok) {

				throw new Error(
					"Text sanitization failed."
				);

			}


			const textProtectedBlob =
				await textResponse.blob();

			/*
			 * STEP 5:
			 * Blur selected license plates.
			 */

			const plateForm =
				new FormData();


			plateForm.append(
				"file",
				textProtectedBlob,
				"privchk_text_clean.jpg"
			);


			const selectedPlates =
				getSelectedPlates();


			plateForm.append(
				"selected_plates",
				JSON.stringify(
					selectedPlates
				)
			);


			const plateResponse =
				await fetch(
					"/api/plates/sanitize",
					{
						method: "POST",
						body: plateForm
					}
				);


			if (!plateResponse.ok) {

				throw new Error(
					"License plate sanitization failed."
				);

			}


			const protectedBlob =
				await plateResponse.blob();
	
            const safeURL =
                URL.createObjectURL(
                    protectedBlob
                );


            protectedImage.src =
                safeURL;


            downloadButton.href =
                safeURL;

            let protectionHtml = `
                <strong>
                    ✓ Protection applied
                </strong>
                <br><br>
            `;

            if (
                lastMetadataScan &&
                lastMetadataScan.metadata_found
            ) {
                protectionHtml +=
                    "✓ Image metadata removed<br>";
            }
            else {
                protectionHtml +=
                    "✓ No image metadata was present<br>";
            }


            const blurredFaceCount =
                getSelectedFaces().length;
			
			const selectedQRCount =
				getSelectedQRCodes().length;
			
			const selectedTextCount =
				getSelectedText().length;		

			const selectedPlateCount =
				selectedPlates.length;				

            if (blurredFaceCount > 0) {

                protectionHtml +=
                    `✓ ${blurredFaceCount} selected ` +
                    `face${
                        blurredFaceCount === 1
                            ? ""
                            : "s"
                    } blurred<br>`;

            }
            else {

                protectionHtml +=
        "✓ No faces selected for blurring<br>";

            }
			
			if (
				selectedQRCount > 0
			) {

				protectionHtml +=
					`✓ ${selectedQRCount} selected ` +
					`QR code${
						selectedQRCount === 1
							? ""
							: "s"
					} blurred<br>`;

			}
			else {

				protectionHtml +=
					"✓ No QR codes selected for protection<br>";

			}			

			if (
				selectedTextCount > 0
			) {

				protectionHtml +=
					`✓ ${selectedTextCount} selected ` +
					`private text region${
						selectedTextCount === 1
							? ""
							: "s"
					} redacted<br>`;

			}
			else {

				protectionHtml +=
					"✓ No private text selected for redaction<br>";

			}
			
			if (
				selectedPlateCount > 0
			) {

				protectionHtml +=
					`✓ ${selectedPlateCount} selected ` +
					`license plate${
						selectedPlateCount === 1
							? ""
							: "s"
					} blurred<br>`;

			}
			else {

				protectionHtml +=
					"✓ No license plates selected for protection<br>";

			}			

            protectionSummary.innerHTML =
                protectionHtml;
	

            protectedSection.classList.remove(
                "hidden"
            );
			requestAnimationFrame(() => {

				protectedSection.scrollIntoView({
					behavior: "smooth",
					block: "start"
				});

				protectedSection.focus({
					preventScroll: true
				});

			});

            protectedSection.scrollIntoView({
                behavior: "smooth"
            });

        }
        catch (error) {

            console.error(error);

            alert(
                "Unable to protect the photo."
            );

        }
        finally {

            protectButton.disabled =
                false;

            protectButton.textContent =
                "Protect Photo";

        }

    }
);


function escapeHtml(value) {

    return value
        .replaceAll(
            "&",
            "&amp;"
        )
        .replaceAll(
            "<",
            "&lt;"
        )
        .replaceAll(
            ">",
            "&gt;"
        )
        .replaceAll(
            '"',
            "&quot;"
        )
        .replaceAll(
            "'",
            "&#039;"
        );
}