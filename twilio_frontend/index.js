import { Device } from '@twilio/voice-sdk';

window.initTwilio = async function(token) {
    const device = new Device(token, { debug: true });

    device.on('ready', () => console.log('Twilio Device Ready'));
    device.on('error', (err) => console.error('Twilio Device Error:', err));
    device.on('incoming', (conn) => {
        console.log('Incoming call from:', conn.parameters.From);
        if (window.onIncomingCall) window.onIncomingCall(conn);
    });

    window.device = device;
    return device;
};
