# app.py

import streamlit as st
import sqlite3
import polars as pl
import plotly.express as px
from datetime import date # Импортируем date из datetime
from datetime import datetime

#DB_PATH = "data/weather.db"
DB_PATH = "weather.db"

st.set_page_config(page_title="WeatherInsight", layout="wide")
st.title("🌦️ WeatherInsight: Погодные тренды")

# Загрузка данных
@st.cache_data
def load_data():
    conn = sqlite3.connect(DB_PATH)
    df = pl.read_database("SELECT * FROM weather ORDER BY date", conn)
    conn.close()
    return df

try:
    df = load_data()
except Exception as e:
    st.error("❌ Не удалось загрузить данные. Убедитесь, что база данных существует и доступна.")
    st.stop()

df = df.with_columns([
    pl.col('date')
    .str.strptime(pl.Date, format='%Y-%m-%d %H:%M:%S')
    .alias('date2'),

    # 1. Категория температуры
    pl.when(pl.col('avg_temp') < 10)
        .then(pl.lit('холодно'))
        .when(pl.col('avg_temp').is_between(10, 25, closed="both"))
        .then(pl.lit('умеренно'))
        .otherwise(pl.lit('жарко'))
        .alias('temp_category'),

    # 2. Уровень осадков
    pl.when(pl.col('total_precip') == 0)
        .then(pl.lit('без осадков'))
        .when(pl.col('total_precip').is_between(0.01, 5, closed="both"))
        .then(pl.lit('небольшие'))
        .otherwise(pl.lit('сильные'))
        .alias('precipitation_level'),
])
# боковая панель
with st.sidebar:

    st.sidebar.header('Настройки отображения детальной статистики')

    page_size = st.sidebar.selectbox(
        'Количество строк на странице',
        options=[10, 25, 50],
        index=1
    )

    cities = sorted(df["city"].unique().to_list())
    selected_city = st.selectbox("Выберите город", cities)
    city_data = df.filter(pl.col("city") == selected_city)
    min_value = city_data.select(pl.col("date").min()).item()
    max_value = city_data.select(pl.col("date").max()).item()

    date_from = st.date_input(label='Первая дата наблюдений:', value=min_value, format="YYYY-MM-DD")
    date_to = st.date_input(label='Крайняя дата наблюдений:', value=max_value, format="YYYY-MM-DD")
    forecast = st.number_input("Выберите срок прогнозирования (дни)", min_value=7, max_value=30, value="min", step=1)

    distribution_type = st.radio(
        "Выберите признак для построения графика распределения:",
        ["temperature", "precipitation", 'wind_speed'],
        index=0
    )

    eda_chart = st.radio(
        "Выберите тип графика для построения распределения:",
        ["Столбчатый", 'Гистограмма'],
        index=0
    )

    comparison_type = st.radio(
        "Выберите погодный показатель для сравнения значений между городами:",
        ["avg_temp", "total_precip", 'avg_wind'],
        index=0
    )
    comparison_chart = st.radio(
        "Выберите вид графика для сравнения показателя между городами:",
        ["Линейный", "Столбчатый", 'Гистограмма'],
        index=0
    )


# Статистика по всем данным
st.subheader("📊 Общая статистика")
total_records = len(df)
unique_cities = df["city"].n_unique()
st.write(f"Всего записей: {total_records}")
st.write(f"Уникальных городов: {unique_cities}")

st.subheader("📋 Данные за выбранный период")
#current_page = 1
observation_data = city_data.filter((pl.col("date") >= str(date_from)) & (pl.col("date") <= str(date_to)))

if not observation_data.is_empty():
    # Отображаем информацию и таблицу
    total_pages = len(observation_data) // page_size + (1 if len(observation_data) % page_size else 0)
    current_page = st.number_input("Выберите страницу для отображения", min_value=1, max_value=total_pages, value="min", step=1)
    st.write(f'Страница **{current_page}** из **{total_pages}**')
    start_idx = (current_page - 1) * page_size
    end_idx = start_idx + page_size
    current_page_df = observation_data.slice(start_idx, page_size)
    st.dataframe(current_page_df.to_pandas())

    fig_temp_hist = px.line(
        observation_data.to_pandas(),
        x="date",
        y="avg_temp",
        title=f"Средняя температура в {selected_city} (выбранный период наблюдений c {date_from} по {date_to})",
        labels={"avg_temp": "Температура (°C)", "date": "Дата"}
    )
    st.plotly_chart(fig_temp_hist)
else:
    st.write(f'За выбранный период данные отсутствуют. Первая дата наблюдений не должна быть раньше {min_value[:10]} и Крайняя дата наблюдений не должна быть позже {max_value[:10]}')

st.subheader("📋 Прогноз")
temp_list = observation_data['avg_temp'].to_list() # список из значений температуры наблюдаемого периода
l = len(temp_list)
forecast_name = []
forecast_list = []

for i in range(forecast):
    forecast_name.append('День ' + str(i+1))
    temp_list.append(sum(temp_list[-1*forecast:])/forecast)

forecast_data = pl.DataFrame({
    'date': forecast_name,
    'avg_temp': temp_list[-1*forecast:]
})

if not forecast_data.is_empty():
    fig_temp_forecast = px.line(
        forecast_data.to_pandas(),
        x="date",
        y="avg_temp",
        title=f"Прогноз средней температуры в {selected_city}. {forecast} дней после {date_to}",
        labels={"avg_temp": "Температура (°C)", "date": "Дата"}
    )
    st.plotly_chart(fig_temp_forecast)

st.subheader("📋 Разведочный анализ данных (EDA)")
distribution_dict = {"temperature": 'avg_temp', "precipitation": 'total_precip', 'wind_speed': 'avg_wind'}
label_dict = {"temperature": 'Температура (°C)', "precipitation": 'Осадки (мм)', 'wind_speed': 'Скорость ветра (м/с)'}
if eda_chart == 'Гистограмма':
    fig = px.histogram(
        observation_data.to_pandas(),
        x="date",
        y=distribution_dict[distribution_type],
        nbins=50,
        title=f"Интерактивное распределение признака '{distribution_type}'. Тип графика '{eda_chart}'",
        labels={distribution_type: label_dict[distribution_type]},
        color_discrete_sequence=['#636EFA']
    )
    fig.update_layout(xaxis_title=label_dict[distribution_type], yaxis_title='Значение')
    st.plotly_chart(fig)
else:
    fig = px.bar(
        observation_data.to_pandas(),
        x="date",
        y=distribution_dict[distribution_type],
        title=f"Интерактивное распределение признака '{distribution_type}'. Тип графика '{eda_chart}'",
        labels={distribution_type: label_dict[distribution_type]},
        color_discrete_sequence=['#636EFA']
    )
    fig.update_layout(xaxis_title=label_dict[distribution_type], yaxis_title='Значение')
    st.plotly_chart(fig)

st.subheader("📋 Сравнение погодных показателей между разными городами")
compare_data = df.filter((pl.col("date") >= str(date_from)) & (pl.col("date") <= str(date_to)))
if comparison_chart == 'Линейный':
    fig = px.line(
        compare_data.to_pandas(),
        x='date',
        y='avg_temp',
        color='city',
        title=f'Сравните погодного показателя "{comparison_type}" между разными городами. Тип графика "{comparison_chart}"',
    )
    st.plotly_chart(fig)
elif comparison_chart == 'Столбчатый':
    fig = px.bar(
        compare_data.to_pandas(),
        x='date',
        y='avg_temp',
        color='city',
        title=f'Сравните погодного показателя "{comparison_type}" между разными городами. Тип графика "{comparison_chart}"',
    )
    st.plotly_chart(fig)
else:
    fig = px.histogram(
        compare_data.to_pandas(),
        x='date',
        y='avg_temp',
        color='city',
        title=f'Сравните погодного показателя "{comparison_type}" между разными городами. Тип графика "{comparison_chart}"',
    )
    st.plotly_chart(fig)



#observation_data = city_data.filter((pl.col("date") >= str(date_from)) & (pl.col("date") <= str(date_to)))

# График температуры для исторических данных


    # Статистика для исторических данных
#    rainy_days_hist = historical_data["is_rainy"].sum()
#    avg_temp_hist = historical_data["avg_temp"].mean()
#    col1, col2 = st.columns(2)
#    col1.metric("Средняя температура (история)", f"{avg_temp_hist:.1f}°C")
#    col2.metric("Дождливых дней (история)", int(rainy_days_hist))

#if not forecast_data.is_empty():
#    fig_temp_forecast = px.line(
#        forecast_data.to_pandas(),
#        x="date",
#        y="avg_temp",
#        title=f"Средняя температура в {selected_city} (прогноз)",
#        labels={"avg_temp": "Температура (°C)", "date": "Дата"}
#    )
#    st.plotly_chart(fig_temp_forecast, use_container_width=True)

    # Статистика для прогноза
#    rainy_days_forecast = forecast_data["is_rainy"].sum()
#    avg_temp_forecast = forecast_data["avg_temp"].mean()
#    col1, col2 = st.columns(2)
#    col1.metric("Средняя температура (прогноз)", f"{avg_temp_forecast:.1f}°C")
#    col2.metric("Дождливых дней (прогноз)", int(rainy_days_forecast))

# Аномалии (в данном случае - дни, отмеченные как дождливые)
# Ты можешь изменить условие для определения аномалий в зависимости от логики detect_anomalies
#anomalies = city_data.filter(pl.col("is_rainy") == 1)  # Пример: аномалия - дождливый день
#if not anomalies.is_empty():
#    st.subheader("⚠️ Аномалии")
#    st.write(f"Найдено {len(anomalies)} аномалий (дождливых дней) в {selected_city}.")
#    st.dataframe(anomalies.to_pandas())
#else:
#    st.info("✅ Аномалии не обнаружены (по критерию 'дождливый день').")

# Таблица последних данных
