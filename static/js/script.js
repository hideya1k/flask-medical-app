document.getElementById('appointement-form').addEventListener('submit', function(event) {
    const name = document.getElementById('name').value;
    const lastname = document.getElementById('lastname').value;
    const email = document.getElementById('email').value;
    const phonenumber = document.getElementById('phonenumber').value;
    const date = document.getElementById('date').value;
    const time = document.getElementById('time').value;

    if (!name || !lastname || !email || !phonenumber || !date || !time) {
        alert('Veuillez remplir tous les champs.');
        event.preventDefault();
    }
});