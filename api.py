from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import time
from rpi_ws281x import Color, PixelStrip, ws

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'light.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Fixed LED strip configuration
LED_PIN = 18
LED_INVERT = False
LED_CHANNEL = 0

# Permutation ranges and increments
led_counts = 100  # Modify as needed
led_freqs = 800000  # Modify as needed
led_dmas = 5  # Modify as needed
led_brightnesses = 100  # Modify as needed
led_strip_types = ws.WS2811_STRIP_GRB

def colorWipe(strip, color, brightness, wait_ms=5):
    for i in range(strip.numPixels()):
        #if i >= 82 and i <= 85:
        #     strip.setPixelColor(i, Color(*led_green))
        #else:
        strip.setPixelColor(i, color)
        strip.setBrightness(brightness)
        strip.show()
        #time.sleep(wait_ms / 1000.0)

# Define the LightState model
class LightState(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    is_on = db.Column(db.Boolean, default=False)
    red = db.Column(db.Integer, default=0)
    green = db.Column(db.Integer, default=0)
    blue = db.Column(db.Integer, default=0)
    brightness = db.Column(db.Integer, default=0)

# Initialize the database
with app.app_context():
    db.create_all()

# Validation function for incoming color data
def validate_color_values(red, green, blue, brightness):
    if not all(isinstance(v, int) for v in [red, green, blue, brightness]):
        print("All values must be integers")
        return False, "All values must be integers"
    if not all(0 <= v <= 255 for v in [red, green, blue]):
        print("Red, Green, Blue values must be between 0 and 255")
        return False, "Red, Green, Blue values must be between 0 and 255"
    if not 1 <= brightness <= 255:
        print("Brightness must be between 1 and 255")
        return False, "Brightness must be between 1 and 255"
    return True, ""

# Route to set the color of the light
@app.route('/color/', methods=['POST'])
def set_color():
    data = request.json
    red = int(data.get('red'))
    green = int(data.get('green'))
    blue = int(data.get('blue'))
    brightness = int(data.get('brightness'))
    print(str("red: " + str(red) + " green: " + str(green) + " blue: " + str(blue) + " brightness: " + str(int(brightness/2.55))))

    if None in (red, green, blue, brightness):
        return jsonify({"error": "Missing color data"}), 400

    valid, message = validate_color_values(red, green, blue, brightness)
    if not valid:
        return jsonify({"error": message}), 400

    # Update light state in the database
    with app.app_context():
        new_state = LightState(is_on=True, red=red, green=green, blue=blue, brightness=(int(brightness/2.55)))
        # Set the current state to be the last active
        db.session.add(new_state)
        db.session.commit()

    # Apply the color settings to the hardware
    colorWipe(strip, Color(red, green, blue), int(brightness/2.55))
    return jsonify({"success": "Color updated successfully"}), 200

# Route to get the current status of the light
@app.route('/status/', methods=['GET'])
def get_status():
    state = LightState.query.order_by(LightState.id.desc()).first()
    if state:
        return jsonify({
            "is_on": state.is_on,
            "red": state.red,
            "green": state.green,
            "blue": state.blue,
            "brightness": int(state.brightness * 2.55)
        }), 200
    else:
        return jsonify({"error": "No state information available"}), 404

# Route to toggle the power state of the light
@app.route('/toggle_power/', methods=['POST'])
def toggle_power():
    with app.app_context():
        try:
            current_state = LightState.query.order_by(LightState.id.desc()).first()
            if current_state.is_on:
                # Turn off the light and unset last_active
                colorWipe(strip, Color(0, 0, 0), 0)
                current_state.is_on = False
                #current_state.last_active = False
                db.session.commit()
                return jsonify({"success": "Light turned off"}), 200
            else:
                # Restore to last active state
                colorWipe(strip, Color(current_state.red, current_state.green, current_state.blue), current_state.brightness)
                current_state.is_on = True
                db.session.commit()
                return jsonify({"success": "Light restored to last active state"}), 200
        except:
            colorWipe(strip, Color(255, 255, 255), 100)
            new_state = LightState(is_on=True, red=255, green=255, blue=255, brightness=100)
            db.session.add(new_state)
            db.session.commit()
            return jsonify({"success": "There wasn't any states to restore, so, I created an initial state. If you didn't just spin this up for the first time, this was probably an error that you need to look into."}), 200

            
if __name__ == '__main__':
    strip = PixelStrip(led_counts, LED_PIN, led_freqs, led_dmas, LED_INVERT, 100, LED_CHANNEL, led_strip_types)
    strip.begin()
    app.run(debug=True, host='0.0.0.0')

