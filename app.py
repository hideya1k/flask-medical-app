from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
import os
import firebase_admin
from firebase_admin import credentials, firestore, auth
import tensorflow as tf
from PIL import Image
import numpy as np


# Initialize Firebase
cred = credentials.Certificate('rendez_vous_file.json')  # Replace with your service account key path
firebase_admin.initialize_app(cred)
db = firestore.client()  # Initialize Firestore client

# Initialize Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Secret key for session management

# Load AI Model
model = tf.keras.models.load_model('projetIA.h5')

# Firebase Functions
def create_user(username, email, password):
    try:
        admin_emails = ['hideyamanaa2002@gmail.com', 'anotheradmin@example.com']
        role = 'admin' if email in admin_emails else 'user'

        # Create Firebase Auth user
        user = auth.create_user(email=email, password=password, display_name=username)
        
        # Store role in Firestore
        users_ref = db.collection('users')
        users_ref.document(user.uid).set({'username': username, 'email': email, 'role': role})
        
        return user.uid
    except Exception as e:
        print(f"Error creating user: {e}")
        return None

def get_user_by_email(email):
    try:
        user = auth.get_user_by_email(email)
        user_data = db.collection('users').document(user.uid).get()
        return user_data.to_dict(), user.uid
    except Exception:
        return None, None

def create_appointment(user_id, patient_name, patient_lastname, patient_email, patient_phonenumber, appointment_date, appointment_time, prediction_label, filename=None):
    appointments_ref = db.collection('appointments')
    appointments_ref.add({
        'user_id': user_id,
        'patient_name': patient_name,
        'patient_lastname': patient_lastname,
        'patient_email': patient_email,
        'patient_phonenumber': patient_phonenumber,
        'appointment_date': appointment_date,
        'appointment_time': appointment_time,
        'filename': filename,
        'prediction': prediction_label
    })

def get_appointments():
    appointments_ref = db.collection('appointments')
    query = appointments_ref.stream()
    
    appointments = []
    for appointment in query:
        data = appointment.to_dict()
        user_id = data['user_id']
        
        # Fetch user details from the 'users' collection
        user_ref = db.collection('users').document(user_id)
        user_data = user_ref.get()
        
        if user_data.exists:
            user_info = user_data.to_dict()
            data['patient_name'] = data.get('patient_name', 'N/A')
            data['patient_lastname'] = data.get('patient_lastname', 'N/A')
            data['nom'] = user_info.get('username', 'N/A')  # Store user username as 'nom'
            data['prenom'] = user_info.get('email', 'N/A')  # Store user email as 'prenom'

        appointments.append(data)
    
    return appointments


    
def store_laboratory_patient_data(patient_id, patientName, phoneNumber, email, test_type, test_result, test_date):
    try:
        print("Attempting to connect to Firestore.")
        laboratory_ref = db.collection('laboratory_patients')
        print("Successfully connected to Firestore.")
        laboratory_ref.add({
            'patient_id': patient_id,
            'patientName': patientName,
            'phoneNumber': phoneNumber,
            'email': email,
            'test_type': test_type,
            'test_result': test_result,
            'test_date': test_date
        })
        print("Data successfully saved to Firestore.")
    except Exception as e:
        print(f"Error storing data: {e}")
        raise
    
# Helper function to store consultation data in Firestore
def store_consultation_data(patient_id, consultation_notes, treatment_plan, follow_up_date):
    consultations_ref = db.collection('consultations')
    consultations_ref.add({
        'patient_id': patient_id,
        'consultation_notes': consultation_notes,
        'treatment_plan': treatment_plan,
        'follow_up_date': follow_up_date
    })

def save_consultation_notes(patient_id, consultation_notes, treatment_plan, follow_up_date):
    try:
        # Reference the patient's document in Firestore
        patient_ref = db.collection('laboratory_patients').document(patient_id)
        # Update the patient document with the new data
        patient_ref.update({
            'consultation_notes': consultation_notes,
            'treatment_plan': treatment_plan,
            'follow_up_date': follow_up_date
        })
        print(f"Notes saved for patient ID {patient_id}.")
    except Exception as e:
        print(f"Error updating Firestore: {e}")
        raise

def fetch_laboratory_patients():
    try:
        # Fetch all patients from Firestore
        patients_ref = db.collection('laboratory_patients')
        patients = [doc.to_dict() for doc in patients_ref.stream()]
        print(f"Fetched {len(patients)} patients from Firestore.")
        return patients
    except Exception as e:
        print(f"Error fetching patients: {e}")
        return []


# Routes
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/save-consultation', methods=['POST'])
def save_consultation():
    patient_id = request.form['patient_id']
    consultation_notes = request.form['consultation_notes']
    treatment_plan = request.form['treatment_plan']
    follow_up_date = request.form['follow_up_date']
    
    # Optionally, save data in the 'consultations' collection for historical tracking
    store_consultation_data(patient_id, consultation_notes, treatment_plan, follow_up_date)

    # Update the patient's document with the new data (optional if you don't want to store it both places)
    save_consultation_notes(patient_id, consultation_notes, treatment_plan, follow_up_date)
    
    # Redirect to the consultation list route without .html (if it's defined as /conso_list)
    return redirect(url_for('conso_list'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('register'))

        user_found, _ = get_user_by_email(email)
        if user_found:
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))

        user_id = create_user(username, email, password)
        if user_id:
            flash('Account created successfully. Please log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Registration failed. Please try again.', 'danger')

    return render_template('register.html')
@app.route('/login', methods=['GET', 'POST'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        selected_service = request.form.get('service')  # Get the selected service

        # Fetch user details from Firestore
        user, user_id = get_user_by_email(email)
        if user:
            user_ref = db.collection('users').document(user_id)
            user_data = user_ref.get()
            
            if user_data.exists:
                role = user_data.to_dict().get('role', 'user')
                session['user_id'] = user_id
                session['user_role'] = role
                flash('Login successful!', 'success')

                # Handle the redirection based on selected service
                if role == 'admin':  # Admin role handling
                    if selected_service == 'diagnostic_imaging':
                        return redirect(url_for('dashboard'))  # Admin dashboard
                    elif selected_service == 'general_consultation':
                        return redirect(url_for('conso_list'))  # Admin consultation list
                    elif selected_service == 'laboratory_services':
                        return redirect(url_for('doctor'))  # Admin doctor page
                    else:
                        return redirect(url_for('dashboard'))  # Default redirection for admin

                else:  # Regular user role handling
                    if selected_service == 'diagnostic_imaging':
                        return redirect(url_for('dashboard'))  # User dashboard (or another default page)
                    elif selected_service == 'general_consultation':
                        return redirect(url_for('consulting'))  # User to consulting page
                    elif selected_service == 'laboratory_services':
                        return redirect(url_for('laboratory'))  # User to laboratory services page
                    else:
                        return redirect(url_for('dashboard'))  # Default redirection for user
                
            else:
                flash('User role not found!', 'danger')
                return redirect(url_for('login'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')

    return render_template('login.html')


@app.route('/conso_list')
def conso_list():
    # This route will be for admin to see the consultation list
    consultations_ref = db.collection('consultations')
    consultations = [doc.to_dict() for doc in consultations_ref.stream()]
    return render_template('conso_list.html', consultations=consultations)
  

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('You need to log in first.', 'danger')
        return redirect(url_for('login'))

    user_id = session['user_id']
    if session['user_role'] == 'admin':
        appointments = get_appointments()  # Fetch all appointments for admin
        return render_template('dashboard.html', appointments=appointments, is_admin=True)
    else:
        # For patients, show only their specific appointment details
        appointments = get_appointments()
        patient_appointments = [appointment for appointment in appointments if appointment['user_id'] == user_id]
        return render_template('dashboard.html', appointments=patient_appointments, is_admin=False)

@app.route('/add-appointment', methods=['POST'])
def add_appointment():
    if request.method == 'POST':
        patient_name = request.form['patient_name']
        patient_lastname = request.form['patient_lastname']
        patient_email = request.form['patient_email']
        patient_phonenumber = request.form['patient_phonenumber']
        appointment_date = request.form['appointment_date']
        appointment_time = request.form['appointment_time']

        file = request.files.get('file')
        prediction_label = "No Image Uploaded"
        filename = None

        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            image = Image.open(file_path).resize((227, 227))
            image = np.array(image) / 255.0
            image = np.expand_dims(image, axis=0)

            prediction = model.predict(image)
            predict_class = np.argmax(prediction)
            prediction_label = "Covid" if predict_class == 1 else "Healthy"

        user_id = session.get('user_id')
        create_appointment(user_id, patient_name, patient_lastname, patient_email, patient_phonenumber, appointment_date, appointment_time, prediction_label, filename)
        return redirect(url_for('response', message="Appointment added successfully!", message_class="alert alert-success"))

@app.route('/response')
def response():
    message = request.args.get('message', '')
    message_class = request.args.get('message_class', 'alert alert-info')
    return render_template('response.html', message=message, message_class=message_class)

@app.route('/assign-admin', methods=['POST'])
def assign_admin():
    if 'user_role' not in session or session['user_role'] != 'admin':
        flash('You are not authorized to perform this action.', 'danger')
        return redirect(url_for('dashboard'))

    user_email = request.form['email']
    user_data = db.collection('users').where('email', '==', user_email).get()

    if user_data:
        for user in user_data:
            user_ref = user.reference
            user_ref.update({'role': 'admin'})
            flash(f'{user_email} has been assigned the admin role.', 'success')
            return redirect(url_for('dashboard'))
    else:
        flash('User not found.', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_role', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/liste_rdv')
def liste_rdv():
    if 'user_id' not in session or session.get('user_role') != 'admin':
        flash("Access denied: Admins only", "error")
        return redirect(url_for('dashboard'))

    appointments = get_appointments()  # Fetch appointments

    return render_template('liste_rdv.html', appointments=appointments)

@app.route('/consulting', methods=['GET', 'POST'])
def consulting():
    if 'user_id' not in session:
        flash('You need to log in first.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Handle form submission for consultation, e.g., adding new consultation notes
        patient_id = request.form['patient_id']
        consultation_notes = request.form['consultation_notes']
        treatment_plan = request.form['treatment_plan']
        follow_up_date = request.form['follow_up_date']

        # Store consultation data in Firestore (or another database)
        store_consultation_data(patient_id, consultation_notes, treatment_plan, follow_up_date)
        
        flash('Consultation details saved successfully.', 'success')
        return redirect(url_for('consulting'))

    return render_template('consulting.html')

@app.route('/laboratory', methods=['GET', 'POST'])
def laboratory():
    if request.method == 'POST':
        try:
            # Get form data from the laboratory submission
            patient_id = request.form.get('patient_id')
            patientName = request.form.get('patientName')
            phoneNumber = request.form.get('phoneNumber')
            email = request.form.get('email')
            test_type = request.form.get('test_type')
            test_result = request.form.get('test_result')
            test_date = request.form.get('test_date')
            
            print(f"Received form data: {patient_id}, {patientName}, {phoneNumber}, {email}, {test_type}, {test_result}, {test_date}")

            # Store laboratory results in Firestore
            store_laboratory_patient_data(patient_id, patientName, phoneNumber, email, test_type, test_result, test_date)
            
            flash('Laboratory results submitted successfully.', 'success')
        except Exception as e:
            print(f"Error processing form: {e}")
            flash('Failed to submit laboratory results.', 'danger')
        
        return redirect(url_for('laboratory'))

    return render_template('laboratory.html')


@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash('You need to log in first.', 'danger')
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_data = db.collection('users').document(user_id).get()

    if user_data.exists:
        user_info = user_data.to_dict()
        return render_template('profile.html', user_info=user_info)
    else:
        flash('User not found.', 'danger')
        return redirect(url_for('login'))

@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        flash('You need to log in first.', 'danger')
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_data = db.collection('users').document(user_id).get()

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Update user information in Firestore and Firebase Auth
        db.collection('users').document(user_id).update({'username': username, 'email': email})

        if password:
            auth.update_user(user_id, password=password)

        flash('Profile updated successfully.', 'success')
        return redirect(url_for('profile'))

    if user_data.exists:
        user_info = user_data.to_dict()
        return render_template('edit_profile.html', user_info=user_info)
    else:
        flash('User not found.', 'danger')
        return redirect(url_for('login'))

@app.route('/delete-appointment/<appointment_id>', methods=['POST'])
def delete_appointment(appointment_id):
    if 'user_id' not in session or session['user_role'] != 'admin':
        flash('You are not authorized to perform this action.', 'danger')
        return redirect(url_for('dashboard'))

    # Delete the appointment from Firestore
    appointment_ref = db.collection('appointments').document(appointment_id)
    appointment_ref.delete()

    flash('Appointment deleted successfully.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/delete-user/<user_id>', methods=['POST'])
def delete_user(user_id):
    if 'user_id' not in session or session['user_role'] != 'admin':
        flash('You are not authorized to perform this action.', 'danger')
        return redirect(url_for('dashboard'))

    # Delete user from Firebase and Firestore
    auth.delete_user(user_id)
    db.collection('users').document(user_id).delete()

    flash('User deleted successfully.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/doctor', methods=['GET', 'POST'])
def doctor():
    if request.method == 'POST':
        try:
            # Get form data from the submitted note form
            patient_id = request.form.get('patient_id')
            consultation_notes = request.form.get('consultation_notes')
            treatment_plan = request.form.get('treatment_plan')
            follow_up_date = request.form.get('follow_up_date')
            
            print(f"Received data: {patient_id}, {consultation_notes}, {treatment_plan}, {follow_up_date}")

            # Validate input data
            if not (patient_id and consultation_notes and treatment_plan and follow_up_date):
                flash('All fields are required to save the note.', 'danger')
            else:
                # Save the notes to Firestore
                save_consultation_notes(patient_id, consultation_notes, treatment_plan, follow_up_date)
                flash('Consultation notes saved successfully.', 'success')
        except Exception as e:
            print(f"Error saving notes: {e}")
            flash('Failed to save consultation notes.', 'danger')
        
        # Redirect back to the dashboard to display updated data
        return redirect(url_for('doctor'))
    
    # Fetch laboratory patients from Firestore
    laboratory_patients = fetch_laboratory_patients()
    return render_template('doctor.html', laboratory_patients=laboratory_patients)



@app.route('/update-appointment/<appointment_id>', methods=['GET', 'POST'])
def update_appointment(appointment_id):
    if 'user_id' not in session:
        flash('You need to log in first.', 'danger')
        return redirect(url_for('login'))

    appointment_ref = db.collection('appointments').document(appointment_id)
    appointment_data = appointment_ref.get()

    if not appointment_data.exists:
        flash('Appointment not found.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        patient_name = request.form['patient_name']
        patient_lastname = request.form['patient_lastname']
        patient_email = request.form['patient_email']
        patient_phonenumber = request.form['patient_phonenumber']
        appointment_date = request.form['appointment_date']
        appointment_time = request.form['appointment_time']

        # Update appointment details in Firestore
        appointment_ref.update({
            'patient_name': patient_name,
            'patient_lastname': patient_lastname,
            'patient_email': patient_email,
            'patient_phonenumber': patient_phonenumber,
            'appointment_date': appointment_date,
            'appointment_time': appointment_time
        })

        flash('Appointment updated successfully.', 'success')
        return redirect(url_for('dashboard'))

    appointment_data = appointment_data.to_dict()
    return render_template('update_appointment.html', appointment=appointment_data)

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        # Here, you would add logic to send a password reset email
        flash('A password reset link has been sent to your email.', 'info')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')

if __name__ == '__main__':
    app.run(debug=True)
