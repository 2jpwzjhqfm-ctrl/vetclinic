# Ветеринарная клиника «Happy Pet»

Веб-сайт ветеринарной клиники на Flask. Проект содержит главную страницу,
страницы с описанием услуг, специалистов, формой записи на приём и контактами.


| Участник                | Страница          | Маршрут        | HTML-файл            |
|-------------------------|-------------------|----------------|----------------------|
| Афанасенко Ксения (Kseniay_boom) | Главная страница  | `/`            | `index.html`         |
| Галкина Жанна (mooooms) | Услуги           | `/services`    | `services.html`      |
| Шендрикова Ульяна (ylianaan) | Специалисты      | `/specialists` | `specialists.html`   |
| Аркадьева Василиса (Vasya) | Запись на приём  | `/appointment` | `appointment.html`   |
| Бортник Марьяна (maryanapro) | Контакты Адреса        | `/contacts`    | `contacts.html`      |


- Python 3.x
- Flask

   ```bash
   git clone [https://github.com/username1/vet-clinic-flask.git](https://github.com/2jpwzjhqfm-ctrl/vetclinic.git)
   cd vet-clinic-flask
   python -m venv venv
   Windows: venv\Scripts\activate
   Linux/Mac: source venv/bin/activate
   pip install -r requirements.txt
   python app.py
   Маршруты

URL	Страница
/	-Главная страница
/services	-Услуги
/specialists-	Специалисты
/appointment	-Запись на приём
/contacts- Контакты Адреса
