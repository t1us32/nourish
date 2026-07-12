import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Bell,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Flame,
  Moon,
  Plus,
  ScanBarcode,
  Sun,
  Trash2,
  Utensils,
  X,
} from "lucide-react";
import "./styles.css";
import "./search.css";

const goals = { calories: 2100, protein: 130, fat: 70, carbs: 230 };

function haptic(duration = 12) {
  navigator.vibrate?.(duration);
}

function App() {
  const today = new Date().toISOString().slice(0, 10);
  const [selectedDate, setSelectedDate] = useState(today);
  const [meals, setMeals] = useState(() => {
    const savedMeals = localStorage.getItem("nourish-meals");
    return savedMeals
      ? JSON.parse(savedMeals).filter((meal) => ![1, 2, 3].includes(meal.id))
      : [];
  });
  const [showModal, setShowModal] = useState(false);
  const [search, setSearch] = useState("");
  const [selectedFood, setSelectedFood] = useState(null);
  const [amount, setAmount] = useState(100);
  const [foodResults, setFoodResults] = useState([]);
  const [searchingFoods, setSearchingFoods] = useState(false);
  const [foodSearchError, setFoodSearchError] = useState("");
  const [recentSearches, setRecentSearches] = useState([]);
  const [pendingFoods, setPendingFoods] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showScanner, setShowScanner] = useState(false);
  const [theme, setTheme] = useState(() => {
    const savedTheme = localStorage.getItem("nourish-theme");
    if (savedTheme) return savedTheme;
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  });
  const touchStart = useRef(null);
  const displayedMeals = meals.filter((meal) => meal.date === selectedDate);
  const displayDate = new Date(`${selectedDate}T12:00:00`);
  const isToday = selectedDate === today;
  const totals = displayedMeals.reduce(
    (sum, meal) => ({
      calories: sum.calories + meal.calories,
      protein: sum.protein + meal.protein,
      fat: sum.fat + meal.fat,
      carbs: sum.carbs + meal.carbs,
    }),
    { calories: 0, protein: 0, fat: 0, carbs: 0 },
  );
  const remaining = Math.max(goals.calories - totals.calories, 0);
  const percent = Math.min((totals.calories / goals.calories) * 100, 100);
  const animatedCalories = useAnimatedNumber(totals.calories);
  const animatedProtein = useAnimatedNumber(totals.protein);
  const animatedFat = useAnimatedNumber(totals.fat);
  const animatedCarbs = useAnimatedNumber(totals.carbs);
  const animatedRemaining = useAnimatedNumber(remaining);

  useEffect(() => {
    localStorage.setItem("nourish-meals", JSON.stringify(meals));
  }, [meals]);

  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 500);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    const themeColor = document.querySelector('meta[name="theme-color"]');
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("nourish-theme", theme);
    if (themeColor) themeColor.content = theme === "dark" ? "#101827" : "#f5f7fb";
  }, [theme]);

  function toggleTheme() {
    haptic();
    setTheme((currentTheme) => (currentTheme === "dark" ? "light" : "dark"));
  }

  useEffect(() => {
    if (!showModal || selectedFood || search.trim().length < 2) {
      setFoodResults([]);
      return;
    }

    const controller = new AbortController();
    const timeout = setTimeout(async () => {
      setSearchingFoods(true);
      try {
        const response = await fetch(
          `/api/foods/search?query=${encodeURIComponent(search.trim())}`,
          { signal: controller.signal },
        );
        const data = await response.json();
        setFoodResults(response.ok ? data.foods : []);
      } catch (error) {
        if (error.name !== "AbortError") setFoodResults([]);
      } finally {
        if (!controller.signal.aborted) setSearchingFoods(false);
      }
    }, 900);

    return () => {
      controller.abort();
      clearTimeout(timeout);
    };
  }, [search, selectedFood, showModal]);

  function changeDay(offset) {
    haptic();
    const date = new Date(`${selectedDate}T12:00:00`);
    date.setDate(date.getDate() + offset);
    setSelectedDate(date.toISOString().slice(0, 10));
  }

  function mealFromSelection() {
    const nutrients = selectedFood.foodNutrients || [];
    const valueFor = (names) =>
      nutrients.find((nutrient) => names.includes(nutrient.nutrientName))
        ?.value || 0;
    const multiplier = Number(amount) / 100;
    return {
      id: crypto.randomUUID?.() || `${Date.now()}-${Math.random()}`,
      date: selectedDate,
      name: selectedFood.description,
      detail: `${amount} g · Added just now`,
      icon: "✦",
      tone: "sky",
      calories: Math.round(valueFor(["Energy"]) * multiplier),
      protein: Math.round(valueFor(["Protein"]) * multiplier),
      fat: Math.round(valueFor(["Total lipid (fat)"]) * multiplier),
      carbs: Math.round(valueFor(["Carbohydrate, by difference"]) * multiplier),
    };
  }

  function addMeal(event) {
    event?.preventDefault();
    const foodsToLog =
      selectedFood && amount
        ? [...pendingFoods, mealFromSelection()]
        : pendingFoods;
    if (!foodsToLog.length) return;
    haptic(18);
    setMeals((currentMeals) => [...currentMeals, ...foodsToLog]);
    setSearch("");
    setSelectedFood(null);
    setAmount(100);
    setPendingFoods([]);
    setShowModal(false);
  }

  function addMore() {
    if (!selectedFood || !amount) return;
    haptic();
    setPendingFoods((currentFoods) => [...currentFoods, mealFromSelection()]);
    setSearch("");
    setSelectedFood(null);
    setAmount(100);
  }

  function openFoodModal() {
    haptic();
    setSearch("");
    setSelectedFood(null);
    setAmount(100);
    setFoodResults([]);
    setPendingFoods([]);
    setShowScanner(false);
    setShowModal(true);
    fetch("/api/foods/recent-searches")
      .then((response) => response.json())
      .then((data) => setRecentSearches(data.searches || []))
      .catch(() => setRecentSearches([]));
  }

  function closeFoodModal() {
    haptic();
    setShowScanner(false);
    setShowModal(false);
  }

  function removeMeal(id) {
    haptic();
    setMeals((currentMeals) => currentMeals.filter((meal) => meal.id !== id));
  }

  function selectFood(food) {
    haptic();
    setSelectedFood(food);
    setSearch(food.description);
    setAmount(100);
    setFoodResults([]);
    fetch("/api/foods/recent-searches", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: food.description }),
    })
      .then((response) => response.json())
      .then((data) => setRecentSearches(data.searches || []))
      .catch(() => {});
  }

  function useScannedBarcode(code) {
    haptic(20);
    setSearch(code);
    setShowScanner(false);
    setSearchingFoods(true);
    setFoodSearchError("");
    fetch(`/api/foods/barcode/${encodeURIComponent(code)}`)
      .then(async (response) => {
        if (!response.ok)
          throw new Error(
            (await response.json()).detail || "Barcode lookup failed.",
          );
        return response.json();
      })
      .then((data) => selectFood(data.food))
      .catch((error) =>
        setFoodSearchError(error.message || "Barcode lookup failed."),
      )
      .finally(() => setSearchingFoods(false));
  }

  function startSwipe(event) {
    const touch = event.touches[0];
    touchStart.current = { x: touch.clientX, y: touch.clientY };
  }

  function endSwipe(event) {
    if (!touchStart.current) return;
    const touch = event.changedTouches[0];
    const horizontalDistance = touch.clientX - touchStart.current.x;
    const verticalDistance = touch.clientY - touchStart.current.y;
    touchStart.current = null;
    if (showModal) {
      if (
        horizontalDistance > 70 &&
        Math.abs(horizontalDistance) > Math.abs(verticalDistance)
      ) {
        closeFoodModal();
      }
      return;
    }
    if (
      horizontalDistance < -70 &&
      Math.abs(horizontalDistance) > Math.abs(verticalDistance)
    )
      openFoodModal();
  }

  return (
    <main onTouchStart={startSwipe} onTouchEnd={endSwipe}>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <Flame size={21} fill="currentColor" />
          </span>
          Nourish
        </div>
        <nav>
          <a className="active" href="#today">
            <span className="nav-icon">⌂</span>Today
          </a>
          <a href="#insights">
            <span className="nav-icon">◌</span>Insights
          </a>
          <a href="#recipes">
            <span className="nav-icon">♧</span>Recipes
          </a>
        </nav>
        <div className="sidebar-bottom">
          <div className="coach-card">
            <span>✦</span>
            <strong>Meet your goal</strong>
            <p>3 days in a row. Keep it up!</p>
          </div>
          <button className="profile">
            <span className="avatar">AM</span>
            <span>
              <b>Alex Morgan</b>
              <small>Personal plan</small>
            </span>
            <ChevronDown size={16} />
          </button>
        </div>
      </aside>

      <section className="content" id="today">
        <div className="mobile-app-header">
          <div className="mobile-appbar">
            <span className="mobile-app-title">Diary</span>
            <ThemeToggle theme={theme} onToggle={toggleTheme} />
          </div>
          <div className="day-picker">
            <button aria-label="Previous day" onClick={() => changeDay(-1)}>
              <ChevronLeft size={19} />
            </button>
            <div>
              <b>
                {isToday
                  ? "Today"
                  : displayDate.toLocaleDateString("en-US", {
                      weekday: "long",
                    })}
              </b>
              <span>
                {displayDate.toLocaleDateString("en-US", {
                  month: "long",
                  day: "numeric",
                })}
              </span>
            </div>
            <button aria-label="Next day" onClick={() => changeDay(1)}>
              <ChevronRight size={19} />
            </button>
          </div>
        </div>
        {isLoading ? (
          <DashboardSkeleton />
        ) : (
          <>
            <header>
              <div>
                <p className="eyebrow">
                  {displayDate
                    .toLocaleDateString("en-US", {
                      weekday: "long",
                      month: "long",
                      day: "numeric",
                    })
                    .toUpperCase()}
                </p>
                <h1>
                  {isToday ? "Good morning, Alex" : "Your daily log"}{" "}
                  <span>✦</span>
                </h1>
                <p className="subtitle">
                  Here is your nutrition snapshot for{" "}
                  {isToday ? "today" : "this day"}.
                </p>
              </div>
              <div className="header-actions">
                <ThemeToggle theme={theme} onToggle={toggleTheme} />
                <button className="circle-button">
                  <Bell size={19} />
                  <i />
                </button>
                <button className="add-button" onClick={openFoodModal}>
                  <Plus size={18} /> Log food
                </button>
              </div>
            </header>

            <section className="hero-grid">
              <div className="calorie-card">
                <div className="card-heading">
                  <div>
                    <p className="section-label">DAILY ENERGY</p>
                    <h2>Calories</h2>
                  </div>
                  <button className="more">•••</button>
                </div>
                <div className="ring-row">
                  <div
                    key={totals.calories}
                    className="calorie-ring"
                    style={{ "--target": `${percent * 3.6}deg` }}
                  >
                    <div className="ring-center">
                      <b>{animatedRemaining.toLocaleString()}</b>
                      <span>left</span>
                    </div>
                  </div>
                  <div className="ring-notes">
                    <div>
                      <span className="blue-dot" />
                      <p>Consumed</p>
                      <b>
                        {animatedCalories.toLocaleString()} <small>kcal</small>
                      </b>
                    </div>
                    <div>
                      <span className="pale-dot" />
                      <p>Daily goal</p>
                      <b>
                        {goals.calories.toLocaleString()} <small>kcal</small>
                      </b>
                    </div>
                  </div>
                </div>
                <div className="goal-line">
                  <span>Daily goal</span>
                  <strong>
                    {animatedCalories.toLocaleString()} <i>/</i>{" "}
                    {goals.calories.toLocaleString()} kcal
                  </strong>
                </div>
                <div className="bar">
                  <i
                    key={totals.calories}
                    className="fill-line"
                    style={{ "--fill": `${percent}%` }}
                  />
                </div>
              </div>
              <div className="quote-card">
                <div className="quote-art">
                  ✦<span>✧</span>
                </div>
                <div className="quote-copy">
                  <span className="section-label">DAILY REMINDER</span>
                  <h2>
                    Fuel your body,
                    <br />
                    free your mind.
                  </h2>
                  <p>Small choices add up to a healthier you.</p>
                </div>
              </div>
            </section>

            <section className="macro-section" id="insights">
              <div className="section-top">
                <div>
                  <p className="section-label">NUTRITION BREAKDOWN</p>
                  <h2>Your macros</h2>
                </div>
                <button className="text-button">
                  View details <span>→</span>
                </button>
              </div>
              <div className="macro-grid">
                <MacroCard
                  label="Protein"
                  value={animatedProtein}
                  goal={goals.protein}
                  unit="g"
                  color="purple"
                  icon="⌁"
                />
                <MacroCard
                  label="Fat"
                  value={animatedFat}
                  goal={goals.fat}
                  unit="g"
                  color="coral"
                  icon="◒"
                />
                <MacroCard
                  label="Carbs"
                  value={animatedCarbs}
                  goal={goals.carbs}
                  unit="g"
                  color="gold"
                  icon="⌇"
                />
              </div>
            </section>

            <section className="food-section">
              <div className="section-top">
                <div>
                  <p className="section-label">
                    {isToday ? "TODAY'S LOG" : "DAILY LOG"}
                  </p>
                  <h2>Recent meals</h2>
                </div>
                <button className="text-button" onClick={openFoodModal}>
                  Add meal <span>+</span>
                </button>
              </div>
              <div className="meal-list">
                {displayedMeals.length ? (
                  displayedMeals.map((meal) => (
                    <div className="meal" key={meal.id}>
                      <span className={`meal-icon ${meal.tone}`}>
                        {meal.icon}
                      </span>
                      <div className="meal-name">
                        <b>{meal.name}</b>
                        <small>{meal.detail}</small>
                      </div>
                      <div className="meal-macro">
                        <b>{meal.protein}g</b>
                        <span>protein</span>
                      </div>
                      <div className="meal-macro">
                        <b>{meal.carbs}g</b>
                        <span>carbs</span>
                      </div>
                      <strong className="meal-calories">
                        {meal.calories}
                        <small> kcal</small>
                      </strong>
                      <button
                        className="delete-meal"
                        onClick={() => removeMeal(meal.id)}
                        aria-label={`Remove ${meal.name}`}
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  ))
                ) : (
                  <div className="empty-log">
                    <Utensils size={22} />
                    <b>No meals logged</b>
                    <span>Add your first meal for this day.</span>
                    <button className="text-button" onClick={openFoodModal}>
                      Log food <span>+</span>
                    </button>
                  </div>
                )}
              </div>
            </section>
          </>
        )}
      </section>
      {showModal && (
        <div className="modal-backdrop">
          <form className="modal" onSubmit={addMeal}>
            <div className="food-entry-header">
              {selectedFood ? (
                <button
                  type="button"
                  className="food-entry-back"
                  onClick={() => {
                    haptic();
                    setSelectedFood(null);
                    setSearch("");
                  }}
                >
                  <ChevronLeft size={19} /> Search
                </button>
              ) : (
                <span className="food-entry-title">Log food</span>
              )}
              <button
                type="button"
                className="food-entry-close"
                onClick={closeFoodModal}
                aria-label="Return to diary"
              >
                <X size={18} />
                <span>Diary</span>
              </button>
            </div>
            {pendingFoods.length > 0 && (
              <div className="pending-foods">
                <strong>Ready to add · {pendingFoods.length}</strong>
                {pendingFoods.map((food) => (
                  <div key={food.id}>
                    <span>{food.name}</span>
                    <small>{food.detail}</small>
                    <button
                      type="button"
                      onClick={() =>
                        setPendingFoods(
                          pendingFoods.filter((item) => item.id !== food.id),
                        )
                      }
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            )}
            {!selectedFood ? (
              <>
                <div className="food-search-row">
                  <label className="food-search-label">
                    <span>Search foods</span>
                    <input
                      autoFocus
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="Chicken, курка, курица, or 482..."
                    />
                  </label>
                  <button
                    type="button"
                    className="barcode-trigger"
                    aria-label="Scan barcode"
                    onClick={() => {
                      haptic();
                      setShowScanner(true);
                    }}
                  >
                    <ScanBarcode size={22} />
                  </button>
                </div>
                {(searchingFoods || foodResults.length > 0) && (
                  <div className="food-results">
                    {searchingFoods && <span>Searching foods...</span>}
                    {foodResults.map((food) => (
                      <button
                        type="button"
                        key={food.fdcId}
                        onClick={() => selectFood(food)}
                      >
                        <b>{food.description}</b>
                        <small>
                          {food.brandOwner || food.dataType} ·{" "}
                          {Math.round(
                            (food.foodNutrients || []).find(
                              (nutrient) => nutrient.nutrientName === "Energy",
                            )?.value || 0,
                          )}{" "}
                          kcal
                          {String(food.fdcId).startsWith("off-")
                            ? " · per 100g"
                            : ""}
                        </small>
                      </button>
                    ))}
                  </div>
                )}
                {!search.trim() && recentSearches.length > 0 && (
                  <section className="recent-searches">
                    <p>Recent searches</p>
                    {recentSearches.map((query) => (
                      <button type="button" key={query} onClick={() => setSearch(query)}>
                        {query}
                      </button>
                    ))}
                  </section>
                )}
                {pendingFoods.length > 0 && (
                  <button className="add-button submit">
                    <Plus size={18} /> Add to today
                  </button>
                )}
              </>
            ) : (
              <>
                <div className="selected-food">
                  <b>{selectedFood.description}</b>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedFood(null);
                      setSearch("");
                    }}
                  >
                    Change
                  </button>
                </div>
                <label className="amount-label">
                  Amount
                  <div className="amount-control">
                    <button
                      type="button"
                      onClick={() =>
                        setAmount(Math.max(1, Number(amount) - 10))
                      }
                    >
                      −
                    </button>
                    <input
                      type="number"
                      min="1"
                      step="1"
                      value={amount}
                      onChange={(e) => setAmount(e.target.value)}
                    />
                    <span>g</span>
                    <button
                      type="button"
                      onClick={() => setAmount(Number(amount) + 10)}
                    >
                      +
                    </button>
                  </div>
                </label>
                <div className="log-actions">
                  <button type="button" className="add-more" onClick={addMore}>
                    Add more
                  </button>
                  <button className="add-button submit">
                    <Plus size={18} /> Add to today
                  </button>
                </div>
              </>
            )}
          </form>
        </div>
      )}
      {showModal && !selectedFood && foodSearchError && (
        <p className="food-search-error">{foodSearchError}</p>
      )}
      {showModal && showScanner && (
        <BarcodeScanner
          onScan={useScannedBarcode}
          onClose={() => setShowScanner(false)}
        />
      )}
    </main>
  );
}

function ThemeToggle({ theme, onToggle }) {
  const isDark = theme === "dark";
  return (
    <button
      type="button"
      className="circle-button theme-toggle"
      onClick={onToggle}
      aria-label={isDark ? "Use light theme" : "Use dark theme"}
      aria-pressed={isDark}
    >
      {isDark ? <Sun size={19} /> : <Moon size={18} />}
    </button>
  );
}

function MacroCard({ label, value, goal, unit, color, icon }) {
  const pct = Math.min((value / goal) * 100, 100);
  return (
    <article className="macro-card">
      <div className="macro-top">
        <span className={`macro-icon ${color}`}>{icon}</span>
        <span className="macro-pct">{Math.round(pct)}%</span>
      </div>
      <h3>{label}</h3>
      <div className="macro-number">
        <b>{value}</b>
        <span>
          {" "}
          / {goal}
          {unit}
        </span>
      </div>
      <div className={`macro-bar ${color}`}>
        <i style={{ width: `${pct}%` }} />
      </div>
      <p>
        {Math.max(goal - value, 0)}
        {unit} remaining
      </p>
    </article>
  );
}

function useAnimatedNumber(value) {
  const [display, setDisplay] = useState(value);
  const previous = useRef(value);

  useEffect(() => {
    const from = previous.current;
    const difference = value - from;
    const startedAt = performance.now();
    let frame;
    const animate = (now) => {
      const progress = Math.min((now - startedAt) / 500, 1);
      const eased = 1 - (1 - progress) ** 3;
      const next = Math.round(from + difference * eased);
      previous.current = next;
      setDisplay(next);
      if (progress < 1) frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [value]);

  return display;
}

function DashboardSkeleton() {
  return (
    <div className="dashboard-skeleton" aria-label="Loading dashboard">
      <div className="skeleton-card skeleton-calories">
        <i />
        <div>
          <i />
          <i />
        </div>
      </div>
      <div className="skeleton-macros">
        <i />
        <i />
        <i />
      </div>
      <div className="skeleton-meal">
        <i />
        <div>
          <i />
          <i />
        </div>
        <i />
      </div>
      <div className="skeleton-wellness">
        <i />
        <i />
      </div>
    </div>
  );
}

function BarcodeScanner({ onScan, onClose }) {
  const [error, setError] = useState("");

  useEffect(() => {
    if (!window.isSecureContext) {
      setError(
        "Camera access requires HTTPS. Open the secure Wi-Fi address shown by the app server.",
      );
      return undefined;
    }
    let scanner;
    let stopped = false;
    import("html5-qrcode")
      .then(({ Html5Qrcode, Html5QrcodeSupportedFormats }) => {
        if (stopped) return;
        scanner = new Html5Qrcode("barcode-reader");
        return scanner.start(
          { facingMode: "environment" },
          {
            fps: 10,
            qrbox: { width: 260, height: 170 },
            aspectRatio: 1.5,
            formatsToSupport: [
              Html5QrcodeSupportedFormats.EAN_13,
              Html5QrcodeSupportedFormats.EAN_8,
              Html5QrcodeSupportedFormats.UPC_A,
              Html5QrcodeSupportedFormats.UPC_E,
            ],
          },
          (decodedText) => {
            if (stopped) return;
            stopped = true;
            // Return to the food form first. The effect cleanup stops the stream.
            onScan(decodedText);
          },
          () => {},
        );
      })
      .catch(() =>
        setError(
          "Camera access is unavailable. Enter the barcode manually instead.",
        ),
      );

    return () => {
      stopped = true;
      scanner?.stop().catch(() => {});
    };
  }, [onScan]);

  return (
    <section className="scanner-screen">
      <button className="scanner-close" onClick={onClose}>
        <X size={20} /> Close scanner
      </button>
      <h2>Scan a barcode</h2>
      <p>Point your camera at the product barcode.</p>
      <div id="barcode-reader" />
      {error && <p className="scanner-error">{error}</p>}
    </section>
  );
}

createRoot(document.getElementById("root")).render(<App />);
