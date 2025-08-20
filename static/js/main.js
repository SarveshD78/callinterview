let device;

async function initTwilio() {
    const res = await fetch('/token');
    const data = await res.json();

    device = new Twilio.Device(data.token, { debug: true });

    device.on('ready', () => {
        console.log('Twilio Device Ready');
    });

    device.on('error', (err) => {
        console.error('Twilio Device Error:', err);
    });
}

document.getElementById('callBtn').addEventListener('click', async () => {
    const number = document.getElementById('candidateNumber').value;
    if (!number) {
        alert('Enter verified candidate number');
        return;
    }

    const res = await fetch('/call', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ to: number })
    });

    const data = await res.json();
    console.log(data);
});

initTwilio();
