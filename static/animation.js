function shouldReduceMotion() {
  if (typeof window === "undefined" || !window.matchMedia) {
    return false;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export class AnimationDirector {
  constructor(element) {
    this.element = element || null;
    this.typewriterTimer = null;
    this.typewriterText = "";
    this.typewriterIndex = 0;
  }

  skip() {
    if (this.typewriterTimer !== null) {
      window.clearTimeout(this.typewriterTimer);
      this.typewriterTimer = null;
    }
    if (!this.element || !this.typewriterText) {
      return;
    }
    this.element.textContent = this.typewriterText;
    this.element.classList.remove("is-animating", "is-typing");
    this.typewriterText = "";
    this.typewriterIndex = 0;
  }

  showCommentary(text, trigger = "default") {
    if (!this.element) {
      return;
    }

    const cleanText = typeof text === "string" ? text.trim() : "";
    this.skip();

    if (!cleanText) {
      this.element.textContent = "";
      this.element.hidden = true;
      this.element.dataset.trigger = trigger || "default";
      return;
    }

    this.element.dataset.trigger = trigger || "default";
    this.element.hidden = false;
    this.element.classList.remove("is-animating", "is-typing");
    void this.element.offsetWidth;

    if (shouldReduceMotion()) {
      this.element.textContent = cleanText;
      return;
    }

    this.typewriterText = cleanText;
    this.typewriterIndex = 0;
    this.element.classList.add("is-typing");
    this.element.classList.add("is-animating");
    this.element.textContent = "";

    const revealNextCharacter = () => {
      this.typewriterIndex += 1;
      this.element.textContent = cleanText.slice(0, this.typewriterIndex);

      if (this.typewriterIndex < cleanText.length) {
        this.typewriterTimer = window.setTimeout(revealNextCharacter, 18);
        return;
      }

      this.typewriterTimer = null;
      this.typewriterText = cleanText;
      this.element.classList.remove("is-typing");
      this.element.classList.remove("is-animating");
      void this.element.offsetWidth;
      this.element.classList.add("is-animating");
    };

    this.typewriterTimer = window.setTimeout(revealNextCharacter, 80);
  }
}

export default AnimationDirector;
